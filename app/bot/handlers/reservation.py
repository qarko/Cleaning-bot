from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
NAME, PHONE, AREA, ADDRESS, ITEM_TYPE, ITEM_SUBTYPE, CLEANING_METHOD, QUANTITY, QUANTITY_INPUT, ITEMS_SUMMARY, DATE, TIME, NOTES, CONFIRM = range(14)


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

    context.user_data["reservation"] = {"items": [], "current_item": {}}
    await update.message.reply_text("📋 새 예약 등록\n\n고객명을 입력해주세요:")
    return NAME


async def name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 1 or len(name) > 20:
        await update.message.reply_text("고객명을 다시 입력해주세요. (1~20자)")
        return NAME
    context.user_data["reservation"]["name"] = name
    await update.message.reply_text("📱 연락처를 입력해주세요:\n(예: 010-1234-5678)")
    return PHONE


async def phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip().replace("-", "").replace(" ", "")

    if not phone.isdigit() or len(phone) != 11 or not phone.startswith("010"):
        await update.message.reply_text(
            "올바른 휴대폰 번호를 입력해주세요.\n(예: 010-1234-5678 또는 01012345678)"
        )
        return PHONE

    # 포맷팅: 010-1234-5678
    formatted = f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"
    context.user_data["reservation"]["phone"] = formatted
    await update.message.reply_text("지역을 선택해주세요:", reply_markup=area_keyboard())
    return AREA


async def area_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    area = query.data.split(":")[1]
    context.user_data["reservation"]["area"] = area
    await query.edit_message_text(f"지역: {AREA_LABELS.get(area, area)}\n\n상세 주소를 입력해주세요:")
    return ADDRESS


async def address_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["reservation"]["address"] = update.message.text.strip()
    context.user_data["reservation"]["current_item"] = {}
    await update.message.reply_text("품목을 선택해주세요:", reply_markup=item_type_keyboard())
    return ITEM_TYPE


async def item_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    item_type = query.data.split(":")[1]
    context.user_data["reservation"]["current_item"] = {"item_type": item_type}

    subtype_kb = item_subtype_keyboard(item_type)
    if subtype_kb:
        await query.edit_message_text(
            f"품목: {ITEM_LABELS[item_type]}\n사이즈를 선택해주세요:",
            reply_markup=subtype_kb,
        )
        return ITEM_SUBTYPE

    if item_type in CLEANING_METHOD_ITEMS:
        await query.edit_message_text("세척 방식을 선택해주세요:", reply_markup=cleaning_method_keyboard())
        return CLEANING_METHOD

    await query.edit_message_text("수량을 선택해주세요:", reply_markup=quantity_keyboard())
    return QUANTITY


async def item_subtype_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    subtype = query.data.split(":")[1]
    context.user_data["reservation"]["current_item"]["item_subtype"] = subtype
    item_type = context.user_data["reservation"]["current_item"]["item_type"]

    if item_type in CLEANING_METHOD_ITEMS:
        await query.edit_message_text("세척 방식을 선택해주세요:", reply_markup=cleaning_method_keyboard())
        return CLEANING_METHOD

    await query.edit_message_text("수량을 선택해주세요:", reply_markup=quantity_keyboard())
    return QUANTITY


async def cleaning_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.split(":")[1]
    context.user_data["reservation"]["current_item"]["cleaning_method"] = method
    await query.edit_message_text("수량을 선택해주세요:", reply_markup=quantity_keyboard())
    return QUANTITY


async def quantity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    qty = query.data.split(":")[1]
    if qty == "more":
        await query.edit_message_text("수량을 직접 입력해주세요:")
        return QUANTITY_INPUT

    context.user_data["reservation"]["current_item"]["quantity"] = int(qty)
    return await add_current_item(query, context)


async def quantity_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text.strip())
        context.user_data["reservation"]["current_item"]["quantity"] = qty
        return await add_current_item_msg(update, context)
    except ValueError:
        await update.message.reply_text("숫자를 입력해주세요:")
        return QUANTITY_INPUT


async def add_current_item(query, context):
    """현재 품목을 목록에 추가하고 요약 표시"""
    data = context.user_data["reservation"]
    item = data["current_item"]

    # 가격 조회
    async with async_session() as db:
        price = await get_price(
            db, item["item_type"],
            item.get("item_subtype"),
            item.get("cleaning_method"),
        )
    item["price"] = price * item.get("quantity", 1)
    item["unit_price"] = price

    data["items"].append(item)
    data["current_item"] = {}

    await query.edit_message_text(
        build_items_summary(data["items"]),
        reply_markup=items_action_keyboard(),
    )
    return ITEMS_SUMMARY


async def add_current_item_msg(update, context):
    """현재 품목을 목록에 추가 (메시지 버전)"""
    data = context.user_data["reservation"]
    item = data["current_item"]

    async with async_session() as db:
        price = await get_price(
            db, item["item_type"],
            item.get("item_subtype"),
            item.get("cleaning_method"),
        )
    item["price"] = price * item.get("quantity", 1)
    item["unit_price"] = price

    data["items"].append(item)
    data["current_item"] = {}

    await update.message.reply_text(
        build_items_summary(data["items"]),
        reply_markup=items_action_keyboard(),
    )
    return ITEMS_SUMMARY


def build_items_summary(items: list) -> str:
    text = "━━━━━━━━━━━━━━\n📦 선택한 품목\n━━━━━━━━━━━━━━\n"
    total = 0
    for i, item in enumerate(items, 1):
        label = ITEM_LABELS.get(item["item_type"], item["item_type"])
        subtype = item.get("item_subtype", "")
        subtype_str = f" {subtype}" if subtype else ""
        method = item.get("cleaning_method")
        method_str = f" {METHOD_LABELS.get(method, '')}" if method else ""
        qty = item.get("quantity", 1)
        price = item.get("price", 0)
        text += f"{i}. {label}{subtype_str}{method_str} x{qty} — {price:,}원\n"
        total += price
    text += f"━━━━━━━━━━━━━━\n합계: {total:,}원"
    return text


def items_action_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ 품목 추가", callback_data="items:add")],
        [InlineKeyboardButton("✅ 선택 완료", callback_data="items:done")],
    ])


async def items_summary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data.split(":")[1]

    if action == "add":
        context.user_data["reservation"]["current_item"] = {}
        await query.edit_message_text("추가할 품목을 선택해주세요:", reply_markup=item_type_keyboard())
        return ITEM_TYPE

    # action == "done"
    await query.edit_message_text("날짜를 선택해주세요:", reply_markup=date_keyboard())
    return DATE


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
    items = data.get("items", [])
    notes = data.get("special_notes") or "없음"
    area = AREA_LABELS.get(data.get("area", ""), "")
    total = sum(i.get("price", 0) for i in items)

    text = (
        "━━━━━━━━━━━━━━\n"
        "📋 예약 확인\n"
        "━━━━━━━━━━━━━━\n"
        f"고객: {data['name']}\n"
        f"연락처: {data['phone']}\n"
        f"지역: {area}\n"
        f"주소: {data.get('address', '-')}\n"
        f"━━━━━━━━━━━━━━\n"
    )
    for i, item in enumerate(items, 1):
        label = ITEM_LABELS.get(item["item_type"], item["item_type"])
        subtype = item.get("item_subtype", "")
        subtype_str = f" {subtype}" if subtype else ""
        method = item.get("cleaning_method")
        method_str = f" {METHOD_LABELS.get(method, '')}" if method else ""
        qty = item.get("quantity", 1)
        price = item.get("price", 0)
        text += f"  {i}. {label}{subtype_str}{method_str} x{qty} — {price:,}원\n"

    text += (
        f"━━━━━━━━━━━━━━\n"
        f"일시: {data['scheduled_date'].strftime('%Y.%m.%d')} {TIME_LABELS[data['scheduled_time']]}\n"
        f"특이사항: {notes}\n"
        f"합계: {total:,}원\n"
        "━━━━━━━━━━━━━━"
    )
    return text


async def show_confirm(query, context):
    data = context.user_data["reservation"]
    data["price"] = sum(i.get("price", 0) for i in data.get("items", []))
    await query.edit_message_text(build_confirm_text(data), reply_markup=confirm_keyboard())
    return CONFIRM


async def show_confirm_msg(update, context):
    data = context.user_data["reservation"]
    data["price"] = sum(i.get("price", 0) for i in data.get("items", []))
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
        context.user_data["reservation"] = {"items": [], "current_item": {}}
        await query.edit_message_text("처음부터 다시 입력합니다.\n\n고객명을 입력해주세요:")
        return NAME

    # action == "yes"
    data = context.user_data["reservation"]
    async with async_session() as db:
        reservation = await create_reservation(db, data)

    items = data.get("items", [])
    items_text = ", ".join(
        f"{ITEM_LABELS.get(i['item_type'], i['item_type'])} x{i.get('quantity', 1)}"
        for i in items
    )
    await query.edit_message_text(
        f"✅ 예약 등록 완료!\n\n"
        f"예약번호: {reservation.reservation_no}\n"
        f"고객: {data['name']}\n"
        f"품목: {items_text}\n"
        f"일시: {data['scheduled_date'].strftime('%Y.%m.%d')} {TIME_LABELS[data['scheduled_time']]}\n"
        f"합계: {data['price']:,}원"
    )

    await notify_group_new_reservation(context.bot, reservation, data)
    context.user_data.pop("reservation", None)
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("reservation", None)
    await update.message.reply_text("예약 등록이 취소되었습니다.")
    return ConversationHandler.END


# 예약 조회

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
        item_text = format_reservation_items(r)
        status = STATUS_LABELS.get(r.status, r.status)
        text += f"\n{TIME_LABELS.get(r.scheduled_time, '')} | {r.customer.name} | {item_text} [{status}]"

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


def format_reservation_items(r) -> str:
    """예약의 품목을 포맷팅"""
    import json
    if r.items_json:
        try:
            items = json.loads(r.items_json)
            parts = []
            for item in items:
                label = ITEM_LABELS.get(item["item_type"], item["item_type"])
                parts.append(f"{label} x{item.get('quantity', 1)}")
            return ", ".join(parts)
        except Exception:
            pass
    # fallback
    return f"{ITEM_LABELS.get(r.item_type, r.item_type)} x{r.quantity}"


async def view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    reservation_no = query.data.split(":")[1]
    async with async_session() as db:
        r = await get_reservation(db, reservation_no)

    if not r:
        await query.edit_message_text("예약을 찾을 수 없습니다.")
        return

    items_text = format_reservation_items(r)
    status = STATUS_LABELS.get(r.status, r.status)
    notes = r.special_notes or "없음"

    text = (
        f"━━━━━━━━━━━━━━\n"
        f"📋 {r.reservation_no}\n"
        f"━━━━━━━━━━━━━━\n"
        f"고객: {r.customer.name}\n"
        f"연락처: {r.customer.phone}\n"
        f"주소: {r.pickup_address or '-'}\n"
        f"품목: {items_text}\n"
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
            ITEMS_SUMMARY: [CallbackQueryHandler(items_summary_callback, pattern=r"^items:")],
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
