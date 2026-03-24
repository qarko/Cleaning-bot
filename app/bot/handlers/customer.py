from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from app.database import async_session
from app.services.reservation_service import get_customer_info, get_customer_reservations
from app.bot.keyboards import ITEM_LABELS


async def customer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("👤 고객 조회\n\n사용법: /customer 홍길동\n또는: /customer 010-1234-5678")
        return

    search = " ".join(context.args)

    async with async_session() as db:
        customer = await get_customer_info(db, search)

    if not customer:
        await update.message.reply_text(f"'{search}' 고객을 찾을 수 없습니다.")
        return

    async with async_session() as db:
        reservations = await get_customer_reservations(db, customer.id)

    text = (
        f"━━━━━━━━━━━━━━\n"
        f"👤 [고객 정보] {customer.name}\n"
        f"━━━━━━━━━━━━━━\n"
        f"연락처: {customer.phone}\n"
        f"주소: {customer.address or '-'}\n"
        f"방문 횟수: {customer.visit_count}회\n"
        f"총 결제: {customer.total_paid:,}원\n"
    )

    if customer.memo:
        text += f"메모: {customer.memo}\n"

    if reservations:
        text += f"━━━━━━━━━━━━━━\n최근 이력:\n"
        for i, r in enumerate(reservations[:5], 1):
            item = ITEM_LABELS.get(r.item_type, r.item_type)
            text += f"{i}. {r.scheduled_date.strftime('%Y.%m.%d')} {item} x{r.quantity} - {r.price:,}원\n"

    text += "━━━━━━━━━━━━━━"
    await update.message.reply_text(text)
