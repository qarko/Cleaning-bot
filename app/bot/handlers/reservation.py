from datetime import datetime
from telegram import Update
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler,
)
from sqlalchemy import select
from app.database import async_session
from app.models.employee import Employee
from app.services.reservation_service import (
    create_reservation, get_today_reservations, get_all_reservations,
    get_reservation, get_price,
)
from app.bot.keyboards import (
    item_type_keyboard, item_subtype_keyboard, quantity_keyboard,
    date_keyboard, time_keyboard, special_notes_keyboard, confirm_keyboard,
    reservation_action_keyboard, reservation_list_keyboard,
    cleaning_method_keyboard, area_keyboard,
    ITEM_LABELS, TIME_LABELS, STATUS_LABELS, METHOD_LABELS, AREA_LABELS,
    CLEANING_METHOD_ITEMS,
)
from app.bot.notifications import notify_group_new_reservation

# Conversation states
NAME, PHONE, AREA, ADDRESS, ITEM_TYPE, ITEM_SUBTYPE, CLEANING_METHOD, QUANTITY, QUANTITY_INPUT, DATE, TIME, NOTES, CONFIRM = range(13)


async def check_auth(update: Update) -> Employee | None:
    user_id = update.effective_user.id
    async with async_session() as db:
        result = await db.execute(select(Employee).where(Employee.telegram_user_id == user_id))
        return result.scalar_one_or_none()


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = await check_auth(update)
    if not employee:
        await update.message.reply_text("먼저 /start 로 등록해주세요.")
        return ConversationHandler.END
    if employee.role != "boss":
        await update.message.reply_text("예약 등록은 사장만 가능합니다.")
        return ConversationHandler.END

    context.user_data["reservation"] = {}
    await update.message.reply_text("📋 새 예약 등록\n\n고객명을 입력해주세요:")
    return NAME


async def name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["reservation"]["name"] = update.message.text.strip()
    await update.message.reply_text("연락처를 입력해주세요:\n(예: 010-1234-5678)")
    return PHONE


async def phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["reservation"]["phone"] = update.message.text.strip()
    await update.message.reply_text("지역을 선택해주세요:", reply_markup=area_keyboard())
    return AREA


async def area_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    area = query.data.split(":")[1]
    context.user_data["reservation"]["area"] = area
    area_label = AREA_LABELS.get(area, area)
    await query.edit_message_text(f"지역: {area_label}\n\n상세 주소를 입력해주세요:")
    return ADDRESS


async def address_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["reservation"]["address"] = update.message.text.strip()
    await update.message.reply_text(
        "━━━━━━━━━━━━━━\n"
        "올그린 대전점 가격표\n"
        "━━━━━━━━━━━━━━\n"
        "카시트 전제품 4만원\n"
        "쌍둥이유모차 5만원\n"
        "웨건 5만원\n"
        "매트리스 4~6만원\n"
        "소파 4~7만원\n"
        "아기띠 2만/1만원\n"
        "━━━━━━━━━━━━━━\n\n"
        "품목을 선택해주세요:",
        reply_markup=item_type_keyboard(),
    )
    return ITEM_TYPE


async def item_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    item_type = query.data.split(":")[1]
    context.user_data["reservation"]["item_type"] = item_type

    subtype_kb = item_subtype_keyboard(item_type)
    if subtype_kb:
        label = ITEM_LABELS[item_type]
        await query.edit_message_text(f"품목: {label}\n\n사이즈를 선택해주세요:", reply_markup=subtype_kb)
        return ITEM_SUBTYPE

    # 사이즈 선택 불필요 → 세척방식 or 수량
    if item_type in CLEANING_METHOD_ITEMS:
        await query.edit_message_text("세척 방식을 선택해주세요:", reply_markup=cleaning_method_keyboard())
        return CLEANING_METHOD

    await query.edit_message_text("수량을 선택해주세요:", reply_markup=quantity_keyboard())
    return QUANTITY


async def item_subtype_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    subtype = query.data.split(":")[1]
    context.user_data["reservation"]["item_subtype"] = subtype

    item_type = context.user_data["reservation"]["item_type"]

    # 매트리스/소파는 세척방식 선택 필요
    if item_type in CLEANING_METHOD_ITEMS:
        await query.edit_message_text("세척 방식을 선택해주세요:", reply_markup=cleaning_method_keyboard())
        return CLEANING_METHOD

    await query.edit_message_text("수량을 선택해주세요:", reply_markup=quantity_keyboard())
    return QUANTITY


async def cleaning_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    method = query.data.split(":")[1]
    context.user_data["reservation"]["cleaning_method"] = method
    await query.edit_message_text("수량을 선택해주세요:", reply_markup=quantity_keyboard())
    return QUANTITY


async def quantity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    qty = query.data.split(":")[1]
    if qty == "more":
        await query.edit_message_text("수량을 직접 입력해주세요:")
        return QUANTITY_INPUT

    context.user_data["reservation"]["quantity"] = int(qty)
    await query.edit_message_text("날짜를 선택해주세요:", reply_markup=date_keyboard())
    return DATE


async def quantity_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text.strip())
        context.user_data["reservation"]["quantity"] = qty
        await update.message.reply_text("날짜를 선택해주세요:", reply_markup=date_keyboard())
        return DATE
    except ValueError:
        await update.message.reply_text("숫자를 입력해주세요:")
        return QUANTITY_INPUT


async def date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("date_next:"):
        next_date = datetime.strptime(query.data.split(":")[1], "%Y-%m-%d")
        await query.edit_message_text("날짜를 선택해주세요:", reply_markup=date_keyboard(next_date))
        return DATE

    date_str = query.data.split(":")[1]
    context.user_data["reservation"]["scheduled_date"] = datetime.strptime(date_str, "%Y-%m-%d").date()
    await query.edit_message_text("시간대를 선택해주세요:", reply_markup=time_keyboard())
    return TIME


async def time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    time_slot = query.data.split(":")[1]
    context.user_data["reservation"]["scheduled_time"] = time_slot
    await query.edit_message_text(
        "특이사항을 입력해주세요:\n(없으면 아래 버튼 클릭)",
        reply_markup=special_notes_keyboard(),
    )
    return NOTES


async def notes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["reservation"]["special_notes"] = None
    return await show_confirm(query, context)


async def notes_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["reservation"]["special_notes"] = update.message.text.strip()
    return await show_confirm_msg(update, context)


def build_confirm_text(data: dict) -> str:
    item_label = ITEM_LABELS.get(data["item_type"], data["item_type"])
    subtype = data.get("item_subtype", "")
    subtype_str = f" {subtype}" if subtype else ""
    method = data.get("cleaning_method")
    method_str = f" {METHOD_LABELS.get(method, '')}" if method else ""
    notes = data.get("special_notes") or "없음"
    area = AREA_LABELS.get(data.get("area", ""), "")
    total = data.get("price", 0)

    return (
        "━━━━━━━━━━━━━━\n"
        "📋 예약 확인\n"
        "━━━━━━━━━━━━━━\n"
        f"고객: {data['name']}\n"
        f"연락처: {data['phone']}\n"
        f"지역: {area}\n"
        f"주소: {data.get('address', '-')}\n"
        f"품목: {item_label}{subtype_str}{method_str} x {data.get('quantity', 1)}\n"
        f"일시: {data['scheduled_date'].strftime('%Y.%m.%d')} {TIME_LABELS[data['scheduled_time']]}\n"
        f"특이사항: {notes}\n"
        f"금액: {total:,}원\n"
        "━━━━━━━━━━━━━━"
    )


async def calc_price(data: dict) -> int:
    async with async_session() as db:
        price = await get_price(
            db,
            data["item_type"],
            data.get("item_subtype"),
            data.get("cleaning_method"),
        )
    return price * data.get("quantity", 1)


async def show_confirm(query, context):
    data = context.user_data["reservation"]
    data["price"] = await calc_price(data)
    await query.edit_message_text(build_confirm_text(data), reply_markup=confirm_keyboard())
    return CONFIRM


async def show_confirm_msg(update, context):
    data = context.user_data["reservation"]
    data["price"] = await calc_price(data)
    await update.message.reply_text(build_confirm_text(data), reply_markup=confirm_keyboard())
    return CONFIRM


async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data.split(":")[1]

    if action == "cancel":
        context.user_data.pop("reservation", None)
        await query.edit_message_text("예약이 취소되었습니다.")
        return ConversationHandler.END

    if action == "edit":
        context.user_data["reservation"] = {}
        await query.edit_message_text("처음부터 다시 입력합니다.\n\n고객명을 입력해주세요:")
        return NAME

    # action == "yes" → 등록
    data = context.user_data["reservation"]
    async with async_session() as db:
        reservation = await create_reservation(db, data)

    item_label = ITEM_LABELS.get(data["item_type"], data["item_type"])
    await query.edit_message_text(
        f"✅ 예약 등록 완료!\n\n"
        f"예약번호: {reservation.reservation_no}\n"
        f"고객: {data['name']} | {item_label} x {data.get('quantity', 1)}\n"
        f"일시: {data['scheduled_date'].strftime('%Y.%m.%d')} {TIME_LABELS[data['scheduled_time']]}"
    )

    # 단체방 알림
    await notify_group_new_reservation(context.bot, reservation, data)

    context.user_data.pop("reservation", None)
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("reservation", None)
    await update.message.reply_text("예약 등록이 취소되었습니다.")
    return ConversationHandler.END


# 예약 조회 명령어들

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = await check_auth(update)
    if not employee:
        await update.message.reply_text("먼저 /start 로 등록해주세요.")
        return

    async with async_session() as db:
        reservations = await get_today_reservations(db)

    if not reservations:
        await update.message.reply_text("오늘 예약이 없습니다.")
        return

    text = f"━━━━━━━━━━━━━━\n📅 오늘의 예약 ({len(reservations)}건)\n━━━━━━━━━━━━━━\n"
    for r in reservations:
        item = ITEM_LABELS.get(r.item_type, r.item_type)
        status = STATUS_LABELS.get(r.status, r.status)
        text += f"\n{TIME_LABELS.get(r.scheduled_time, '')} | {r.customer.name} | {item} x{r.quantity} [{status}]"

    await update.message.reply_text(text, reply_markup=reservation_list_keyboard(reservations))


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = await check_auth(update)
    if not employee:
        await update.message.reply_text("먼저 /start 로 등록해주세요.")
        return

    async with async_session() as db:
        reservations = await get_all_reservations(db)

    if not reservations:
        await update.message.reply_text("등록된 예약이 없습니다.")
        return

    text = f"━━━━━━━━━━━━━━\n📝 전체 예약 (최근 {len(reservations)}건)\n━━━━━━━━━━━━━━"
    await update.message.reply_text(text, reply_markup=reservation_list_keyboard(reservations))


async def view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    reservation_no = query.data.split(":")[1]
    async with async_session() as db:
        r = await get_reservation(db, reservation_no)

    if not r:
        await query.edit_message_text("예약을 찾을 수 없습니다.")
        return

    item = ITEM_LABELS.get(r.item_type, r.item_type)
    subtype = f" {r.item_subtype}" if r.item_subtype else ""
    status = STATUS_LABELS.get(r.status, r.status)
    notes = r.special_notes or "없음"

    text = (
        f"━━━━━━━━━━━━━━\n"
        f"📋 {r.reservation_no}\n"
        f"━━━━━━━━━━━━━━\n"
        f"고객: {r.customer.name}\n"
        f"연락처: {r.customer.phone}\n"
        f"주소: {r.pickup_address or '-'}\n"
        f"품목: {item}{subtype} x {r.quantity}\n"
        f"일시: {r.scheduled_date.strftime('%Y.%m.%d')} {TIME_LABELS.get(r.scheduled_time, r.scheduled_time)}\n"
        f"특이사항: {notes}\n"
        f"금액: {r.price:,}원\n"
        f"상태: [{status}]\n"
        f"━━━━━━━━━━━━━━"
    )
    await query.edit_message_text(text, reply_markup=reservation_action_keyboard(r.reservation_no, r.status))


def get_reservation_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler("new", new_command),
            MessageHandler(filters.Regex(r"^📋 새 예약$"), new_command),
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_input)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_input)],
            AREA: [CallbackQueryHandler(area_callback, pattern=r"^area:")],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_input)],
            ITEM_TYPE: [CallbackQueryHandler(item_type_callback, pattern=r"^item:")],
            ITEM_SUBTYPE: [CallbackQueryHandler(item_subtype_callback, pattern=r"^subtype:")],
            CLEANING_METHOD: [CallbackQueryHandler(cleaning_method_callback, pattern=r"^method:")],
            QUANTITY: [CallbackQueryHandler(quantity_callback, pattern=r"^qty:")],
            QUANTITY_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, quantity_input)],
            DATE: [CallbackQueryHandler(date_callback, pattern=r"^date")],
            TIME: [CallbackQueryHandler(time_callback, pattern=r"^time:")],
            NOTES: [
                CallbackQueryHandler(notes_callback, pattern=r"^notes:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, notes_input),
            ],
            CONFIRM: [CallbackQueryHandler(confirm_callback, pattern=r"^confirm:")],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )
