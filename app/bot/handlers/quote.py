from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from app.database import async_session
from app.services.reservation_service import get_price
from app.bot.keyboards import item_type_keyboard, item_subtype_keyboard, quantity_keyboard, ITEM_LABELS


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quote"] = {}
    await update.message.reply_text("💰 견적 계산기\n\n품목을 선택해주세요:", reply_markup=item_type_keyboard())


async def quote_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    item_type = query.data.split(":")[1]
    context.user_data.setdefault("quote", {})["item_type"] = item_type

    subtype_kb = item_subtype_keyboard(item_type)
    if subtype_kb:
        await query.edit_message_text(
            f"품목: {ITEM_LABELS[item_type]}\n종류를 선택해주세요:",
            reply_markup=subtype_kb,
        )
    else:
        await query.edit_message_text("수량을 선택해주세요:", reply_markup=quantity_keyboard())


async def quote_subtype_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    subtype = query.data.split(":")[1]
    context.user_data["quote"]["item_subtype"] = subtype
    await query.edit_message_text("수량을 선택해주세요:", reply_markup=quantity_keyboard())


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

    text = (
        f"━━━━━━━━━━━━━━\n"
        f"💰 견적\n"
        f"━━━━━━━━━━━━━━\n"
        f"품목: {item_label}{subtype_str}\n"
        f"수량: {qty}개\n"
        f"단가: {unit_price:,}원\n"
        f"합계: {total:,}원\n"
        f"━━━━━━━━━━━━━━"
    )

    if unit_price == 0:
        text += "\n\n⚠️ 가격이 미등록된 품목입니다. /start 후 가격을 설정해주세요."

    await query.edit_message_text(text)
    context.user_data.pop("quote", None)
