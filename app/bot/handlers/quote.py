from telegram import Update
from telegram.ext import ContextTypes
from app.database import async_session
from app.services.reservation_service import get_price
from app.bot.keyboards import item_type_keyboard, item_subtype_keyboard, quantity_keyboard, ITEM_LABELS, CLEANING_METHOD_ITEMS, cleaning_method_keyboard, METHOD_LABELS
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# 견적 전용 키보드 (q_ 접두사로 예약과 구분)
def q_item_type_keyboard():
    kb = item_type_keyboard()
    buttons = []
    for row in kb.inline_keyboard:
        new_row = []
        for btn in row:
            new_row.append(InlineKeyboardButton(btn.text, callback_data=btn.callback_data.replace("item:", "q_item:")))
        buttons.append(new_row)
    return InlineKeyboardMarkup(buttons)


def q_subtype_keyboard(item_type: str):
    kb = item_subtype_keyboard(item_type)
    if not kb:
        return None
    buttons = []
    for row in kb.inline_keyboard:
        new_row = []
        for btn in row:
            new_row.append(InlineKeyboardButton(btn.text, callback_data=btn.callback_data.replace("subtype:", "q_sub:")))
        buttons.append(new_row)
    return InlineKeyboardMarkup(buttons)


def q_method_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("건식 세척", callback_data="q_method:dry"),
            InlineKeyboardButton("습식 세척", callback_data="q_method:wet"),
        ],
    ])


def q_quantity_keyboard():
    kb = quantity_keyboard()
    buttons = []
    for row in kb.inline_keyboard:
        new_row = []
        for btn in row:
            new_row.append(InlineKeyboardButton(btn.text, callback_data=btn.callback_data.replace("qty:", "q_qty:")))
        buttons.append(new_row)
    return InlineKeyboardMarkup(buttons)


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quote"] = {}
    await update.message.reply_text("💰 견적 계산기\n\n품목을 선택해주세요:", reply_markup=q_item_type_keyboard())


async def quote_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    item_type = query.data.split(":")[1]
    context.user_data.setdefault("quote", {})["item_type"] = item_type

    subtype_kb = q_subtype_keyboard(item_type)
    if subtype_kb:
        await query.edit_message_text(
            f"품목: {ITEM_LABELS[item_type]}\n종류를 선택해주세요:",
            reply_markup=subtype_kb,
        )
    elif item_type in CLEANING_METHOD_ITEMS:
        await query.edit_message_text("세척 방식을 선택해주세요:", reply_markup=q_method_keyboard())
    else:
        await query.edit_message_text("수량을 선택해주세요:", reply_markup=q_quantity_keyboard())


async def quote_subtype_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    subtype = query.data.split(":")[1]
    context.user_data["quote"]["item_subtype"] = subtype

    item_type = context.user_data["quote"].get("item_type", "")
    if item_type in CLEANING_METHOD_ITEMS:
        await query.edit_message_text("세척 방식을 선택해주세요:", reply_markup=q_method_keyboard())
    else:
        await query.edit_message_text("수량을 선택해주세요:", reply_markup=q_quantity_keyboard())


async def quote_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    method = query.data.split(":")[1]
    context.user_data["quote"]["cleaning_method"] = method
    await query.edit_message_text("수량을 선택해주세요:", reply_markup=q_quantity_keyboard())


async def quote_qty_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    qty_str = query.data.split(":")[1]
    if qty_str == "more":
        qty = 5
    else:
        qty = int(qty_str)

    quote = context.user_data.get("quote", {})
    item_type = quote.get("item_type", "")
    item_subtype = quote.get("item_subtype")

    async with async_session() as db:
        unit_price = await get_price(db, item_type, item_subtype)

    total = unit_price * qty
    item_label = ITEM_LABELS.get(item_type, item_type)
    subtype_str = f" ({item_subtype})" if item_subtype else ""
    method = quote.get("cleaning_method")
    method_str = f" {METHOD_LABELS.get(method, '')}" if method else ""

    text = (
        f"━━━━━━━━━━━━━━\n"
        f"💰 견적\n"
        f"━━━━━━━━━━━━━━\n"
        f"품목: {item_label}{subtype_str}{method_str}\n"
        f"수량: {qty}개\n"
        f"단가: {unit_price:,}원\n"
        f"합계: {total:,}원\n"
        f"━━━━━━━━━━━━━━"
    )

    if unit_price == 0:
        text += "\n\n⚠️ 가격이 미등록된 품목입니다."

    await query.edit_message_text(text)
    context.user_data.pop("quote", None)
