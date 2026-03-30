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
    reservation_list_keyboard, cancel_confirm_keyboard,
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

# 상태 전환 유효성 맵: 현재 상태 → 허용되는 다음 상태
VALID_TRANSITIONS = {
    "pending":     {"confirm", "confirmed", "cancel", "cancelconfirm"},
    "confirmed":   {"picking_up", "cancel", "cancelconfirm"},
    "picking_up":  {"picked_up", "cancel", "cancelconfirm"},
    "picked_up":   {"cleaning", "cancel", "cancelconfirm"},
    "cleaning":    {"cleaned", "cancel", "cancelconfirm"},
    "cleaned":     {"delivering", "cancel", "cancelconfirm"},
    "delivering":  {"delivered", "cancel", "cancelconfirm"},
    "delivered":   {"settle", "cancel", "cancelconfirm"},
    "settled":     set(),   # 최종 상태 — 변경 불가
    "cancelled":   set(),   # 최종 상태 — 변경 불가
}


async def get_employee(user_id: int) -> Employee | None:
    async with async_session() as db:
        result = await db.execute(select(Employee).where(Employee.telegram_user_id == user_id))
        return result.scalar_one_or_none()


async def action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    if len(parts) < 3:
        return
    # action:<status>:<reservation_no>
    action = parts[1]
    reservation_no = parts[2]

    employee = await get_employee(update.effective_user.id)
    if not employee:
        await query.edit_message_text("먼저 /start 로 등록해주세요.")
        return

    # 상태 전환 유효성 검사
    async with async_session() as db:
        current = await get_reservation(db, reservation_no)
    if current:
        allowed = VALID_TRANSITIONS.get(current.status, set())
        if action not in allowed:
            status_label = STATUS_LABELS.get(current.status, current.status)
            await query.edit_message_text(
                f"⚠️ 현재 상태({status_label})에서는 이 작업을 수행할 수 없습니다.",
                reply_markup=reservation_action_keyboard(current.reservation_no, current.status, role=employee.role),
            )
            return

    # 정산 처리
    if action == "settle":
        async with async_session() as db:
            r = await get_reservation(db, reservation_no)
        if r and r.payment_method:
            # 예약 시 결제 방법이 지정된 경우 → 확인 후 정산
            method_label = PAYMENT_LABELS.get(r.payment_method, r.payment_method)
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            confirm_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ {method_label}로 정산 확인", callback_data=f"pay:{r.payment_method}:{reservation_no}")],
                [InlineKeyboardButton("결제 방법 변경", callback_data=f"pay:change:{reservation_no}")],
            ])
            await query.edit_message_text(
                f"결제 방법: {method_label}\n금액: {r.price:,}원\n\n결제를 확인해주세요:",
                reply_markup=confirm_kb,
            )
        else:
            await query.edit_message_text(
                "결제 방법을 선택해주세요:",
                reply_markup=payment_method_keyboard(reservation_no),
            )
        return

    # 취소 확인 단계
    if action == "cancelconfirm":
        await query.edit_message_text(
            f"⚠️ {reservation_no} 예약을 정말 취소하시겠습니까?",
            reply_markup=cancel_confirm_keyboard(reservation_no),
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
            display = r.pickup_address or (r.customer.phone if r.customer else "")
            await query.edit_message_text(
                f"✅ {reservation_no} 예약 확정!\n"
                f"{display} | {item} x{r.quantity}",
                reply_markup=reservation_action_keyboard(r.reservation_no, r.status, role=employee.role),
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
        # 세척완료 시 배송 예정일 선택으로 분기
        if action == "cleaned":
            context.user_data["pending_action"] = {
                "status": action,
                "reservation_no": reservation_no,
                "employee_id": employee.id,
                "employee_name": employee.name,
                "employee_role": employee.role,
                "step": "delivery_date",
            }
            from app.bot.keyboards import date_keyboard
            await query.edit_message_text(
                "📦 배송 예정일을 선택해주세요:",
                reply_markup=date_keyboard(),
            )
            return

        await query.edit_message_text(
            f"📸 사진을 업로드해주세요.\n(건너뛰려면 아무 텍스트 입력)",
        )
        return

    # 사진 불필요한 상태 변경
    async with async_session() as db:
        r = await update_reservation_status(db, reservation_no, action)
    if r:
        status_label = STATUS_LABELS.get(action, action)
        address = r.pickup_address or reservation_no
        await query.edit_message_text(
            f"✅ {address} → {status_label}",
            reply_markup=reservation_action_keyboard(r.reservation_no, r.status, role=employee.role),
        )
        await notify_group_status_change(context.bot, r, action, employee.name, sender_role=employee.role, photo_url=None)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get("pending_action")
    if not pending:
        # pending_action이 없으면 네이버 예약 캡쳐로 처리
        from app.bot.handlers.naver_ocr import naver_photo_handler
        await naver_photo_handler(update, context)
        return

    photo_url = None
    memo = update.message.caption  # 사진과 함께 보낸 텍스트
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_url = file.file_path  # TODO: Cloudinary 업로드로 교체

    reservation_no = pending["reservation_no"]
    status = pending["status"]
    stage = STATUS_STAGE_MAP.get(status)

    async with async_session() as db:
        r = await get_reservation(db, reservation_no)
        if r and stage:
            await add_task_update(db, r.id, stage, pending["employee_id"], photo_url, memo=memo)
        r = await update_reservation_status(db, reservation_no, status)

    if r:
        status_label = STATUS_LABELS.get(status, status)
        address = r.pickup_address or reservation_no
        photo_text = " (사진 첨부)" if photo_url else ""
        delivery_text = ""
        if pending.get("delivery_date"):
            delivery_text = f"\n📦 배송 예정: {pending['delivery_date']}"
        await update.message.reply_text(
            f"✅ {address} → {status_label}{photo_text}{delivery_text}",
            reply_markup=reservation_action_keyboard(r.reservation_no, r.status, role=pending.get("employee_role", "staff")),
        )
        await notify_group_status_change(
            context.bot, r, status, pending["employee_name"],
            sender_role=pending.get("employee_role", ""),
            photo_url=photo_url,
            delivery_date=pending.get("delivery_date"),
        )

    context.user_data.pop("pending_action", None)


async def skip_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """사진 건너뛰기 또는 메모 입력 - pending_action이 있을 때만 동작"""
    pending = context.user_data.get("pending_action")
    if not pending:
        return  # pending_action이 없으면 무시

    reservation_no = pending["reservation_no"]
    status = pending["status"]
    stage = STATUS_STAGE_MAP.get(status)
    memo = update.message.text.strip() if update.message.text else None

    async with async_session() as db:
        r = await get_reservation(db, reservation_no)
        if r and stage:
            await add_task_update(db, r.id, stage, pending["employee_id"], memo=memo)
        r = await update_reservation_status(db, reservation_no, status)

    if r:
        status_label = STATUS_LABELS.get(status, status)
        address = r.pickup_address or reservation_no
        delivery_text = ""
        if pending.get("delivery_date"):
            delivery_text = f"\n📦 배송 예정: {pending['delivery_date']}"
        memo_text = f"\n메모: {memo}" if memo else ""
        await update.message.reply_text(
            f"✅ {address} → {status_label}{delivery_text}{memo_text}",
            reply_markup=reservation_action_keyboard(r.reservation_no, r.status, role=pending.get("employee_role", "staff")),
        )
        await notify_group_status_change(
            context.bot, r, status, pending["employee_name"],
            sender_role=pending.get("employee_role", ""),
            delivery_date=pending.get("delivery_date"),
        )

    context.user_data.pop("pending_action", None)


async def delivery_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """세척 완료 후 배송 예정일 선택"""
    query = update.callback_query
    await query.answer()

    pending = context.user_data.get("pending_action")
    if not pending or pending.get("step") != "delivery_date":
        return

    if query.data.startswith("date_next:"):
        from app.bot.keyboards import date_keyboard
        from datetime import datetime
        next_date = datetime.strptime(query.data.split(":")[1], "%Y-%m-%d")
        await query.edit_message_text("📦 배송 예정일을 선택해주세요:", reply_markup=date_keyboard(next_date))
        return

    date_str = query.data.split(":")[1]
    pending["delivery_date"] = date_str
    pending["step"] = "photo"

    await query.edit_message_text(
        f"배송 예정일: {date_str}\n\n📸 세척 완료 사진을 업로드해주세요.\n(건너뛰려면 아무 텍스트 입력)\n\n💡 특이사항이 있으면 함께 입력해주세요.",
    )


async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    # pay:<method>:<reservation_no>
    method = parts[1]
    reservation_no = parts[2]

    # 결제 방법 변경 요청
    if method == "change":
        await query.edit_message_text(
            "결제 방법을 선택해주세요:",
            reply_markup=payment_method_keyboard(reservation_no),
        )
        return

    # 정산 중복 방어
    async with async_session() as db:
        check = await get_reservation(db, reservation_no)
    if check and check.status == "settled":
        await query.edit_message_text(f"이미 정산 완료된 예약입니다. ({reservation_no})")
        return

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
        display = r.pickup_address or (r.customer.phone if r.customer else "")
        text += f"\n{TIME_LABELS.get(r.scheduled_time, '')} | {display} | {item} [{status}]"

    await update.message.reply_text(text, reply_markup=reservation_list_keyboard(active))
