from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from sqlalchemy import select
from app.database import async_session
from app.models.employee import Employee
from app.models.reservation import Reservation
from app.services.reservation_service import (
    get_reservation, update_reservation_status, add_task_update,
    settle_reservation, get_today_reservations,
)
from app.bot.keyboards import (
    reservation_action_keyboard, payment_method_keyboard,
    reservation_list_keyboard,
    ITEM_LABELS, TIME_LABELS, STATUS_LABELS, PAYMENT_LABELS,
)
from app.bot.notifications import notify_group_status_change

# 상태 변경 매핑
STATUS_STAGE_MAP = {
    "picking_up": None,
    "picked_up": "pickup",
    "cleaning": None,
    "cleaned": "clean",
    "delivering": None,
    "delivered": "delivery",
}

PHOTO_STAGES = {"picked_up", "cleaned", "delivered"}


async def get_employee(user_id: int) -> Employee | None:
    async with async_session() as db:
        result = await db.execute(select(Employee).where(Employee.telegram_user_id == user_id))
        return result.scalar_one_or_none()


async def action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    # action:<status>:<reservation_no>
    action = parts[1]
    reservation_no = parts[2]

    employee = await get_employee(update.effective_user.id)
    if not employee:
        await query.edit_message_text("먼저 /start 로 등록해주세요.")
        return

    # 정산 처리
    if action == "settle":
        await query.edit_message_text(
            "결제 방법을 선택해주세요:",
            reply_markup=payment_method_keyboard(reservation_no),
        )
        return

    # 취소 처리
    if action == "cancel":
        async with async_session() as db:
            r = await update_reservation_status(db, reservation_no, "cancelled")
        if r:
            await query.edit_message_text(f"❌ {reservation_no} 예약이 취소되었습니다.")
            await notify_group_status_change(context.bot, r, "cancelled", employee.name, sender_role=employee.role)
        return

    # 확정
    if action == "confirm":
        async with async_session() as db:
            r = await update_reservation_status(db, reservation_no, "confirmed")
        if r:
            item = ITEM_LABELS.get(r.item_type, r.item_type)
            await query.edit_message_text(
                f"✅ {reservation_no} 예약 확정!\n"
                f"고객: {r.customer.name} | {item} x{r.quantity}",
                reply_markup=reservation_action_keyboard(r.reservation_no, r.status),
            )
            await notify_group_status_change(context.bot, r, "confirmed", employee.name, sender_role=employee.role)
        return

    # 사진이 필요한 단계인지 확인
    if action in PHOTO_STAGES:
        context.user_data["pending_action"] = {
            "status": action,
            "reservation_no": reservation_no,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "employee_role": employee.role,
        }
        await query.edit_message_text(
            f"📸 사진을 업로드해주세요.\n(건너뛰려면 아무 텍스트 입력)",
        )
        return

    # 사진 불필요한 상태 변경
    async with async_session() as db:
        r = await update_reservation_status(db, reservation_no, action)
    if r:
        status_label = STATUS_LABELS.get(action, action)
        await query.edit_message_text(
            f"✅ {reservation_no} → {status_label}",
            reply_markup=reservation_action_keyboard(r.reservation_no, r.status),
        )
        await notify_group_status_change(context.bot, r, action, employee.name, sender_role=employee.role)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get("pending_action")
    if not pending:
        return

    photo_url = None
    if update.message.photo:
        # 가장 큰 사진 가져오기
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_url = file.file_path  # TODO: Cloudinary 업로드로 교체

    reservation_no = pending["reservation_no"]
    status = pending["status"]
    stage = STATUS_STAGE_MAP.get(status)

    async with async_session() as db:
        r = await get_reservation(db, reservation_no)
        if r and stage:
            await add_task_update(db, r.id, stage, pending["employee_id"], photo_url)
        r = await update_reservation_status(db, reservation_no, status)

    if r:
        status_label = STATUS_LABELS.get(status, status)
        photo_text = " (사진 첨부)" if photo_url else ""
        await update.message.reply_text(
            f"✅ {reservation_no} → {status_label}{photo_text}",
            reply_markup=reservation_action_keyboard(r.reservation_no, r.status),
        )
        await notify_group_status_change(context.bot, r, status, pending["employee_name"], sender_role=pending.get("employee_role", ""))

    context.user_data.pop("pending_action", None)


async def skip_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """사진 건너뛰기 - pending_action이 있을 때만 동작"""
    pending = context.user_data.get("pending_action")
    if not pending:
        return  # pending_action이 없으면 무시

    reservation_no = pending["reservation_no"]
    status = pending["status"]
    stage = STATUS_STAGE_MAP.get(status)

    async with async_session() as db:
        r = await get_reservation(db, reservation_no)
        if r and stage:
            await add_task_update(db, r.id, stage, pending["employee_id"])
        r = await update_reservation_status(db, reservation_no, status)

    if r:
        status_label = STATUS_LABELS.get(status, status)
        await update.message.reply_text(
            f"✅ {reservation_no} → {status_label}",
            reply_markup=reservation_action_keyboard(r.reservation_no, r.status),
        )
        await notify_group_status_change(context.bot, r, status, pending["employee_name"], sender_role=pending.get("employee_role", ""))

    context.user_data.pop("pending_action", None)


async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    # pay:<method>:<reservation_no>
    method = parts[1]
    reservation_no = parts[2]

    async with async_session() as db:
        payment = await settle_reservation(db, reservation_no, method)

    if payment:
        method_label = PAYMENT_LABELS.get(method, method)
        await query.edit_message_text(
            f"💰 정산 완료!\n\n"
            f"예약: {reservation_no}\n"
            f"금액: {payment.amount:,}원\n"
            f"결제: {method_label}"
        )
        employee = await get_employee(update.effective_user.id)
        async with async_session() as db:
            r = await get_reservation(db, reservation_no)
        if r:
            await notify_group_status_change(context.bot, r, "settled", employee.name if employee else "")
    else:
        await query.edit_message_text("정산 처리 중 오류가 발생했습니다.")


async def mytasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = await get_employee(update.effective_user.id)
    if not employee:
        await update.message.reply_text("먼저 /start 로 등록해주세요.")
        return

    async with async_session() as db:
        reservations = await get_today_reservations(db)

    # 완료되지 않은 작업만 필터
    active = [r for r in reservations if r.status not in ("settled", "cancelled", "delivered")]

    if not active:
        await update.message.reply_text("📌 오늘 할 일이 없습니다!")
        return

    text = f"━━━━━━━━━━━━━━\n📌 오늘 할 일 ({len(active)}건)\n━━━━━━━━━━━━━━"
    for r in active:
        item = ITEM_LABELS.get(r.item_type, r.item_type)
        status = STATUS_LABELS.get(r.status, r.status)
        text += f"\n{TIME_LABELS.get(r.scheduled_time, '')} | {r.customer.name} | {item} [{status}]"

    await update.message.reply_text(text, reply_markup=reservation_list_keyboard(active))
