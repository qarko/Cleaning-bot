"""메뉴 버튼 텍스트 핸들러 - ReplyKeyboard 버튼 클릭 시 명령어 실행
  NOTE: '📋 새 예약'은 ConversationHandler entry_point에서 직접 처리"""
from telegram import Update
from telegram.ext import ContextTypes
from app.bot.handlers.reservation import today_command, tomorrow_command, list_command
from app.bot.handlers.task import mytasks_command
from app.bot.handlers.quote import quote_command


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    handlers = {
        "📅 오늘 예약": today_command,
        "📆 내일 예약": tomorrow_command,
        "📝 전체 예약": list_command,
        "📌 할 일": mytasks_command,
        "💰 견적 계산": quote_command,
    }

    handler = handlers.get(text)
    if handler:
        return await handler(update, context)

    if text == "👤 고객 조회":
        await update.message.reply_text("고객명 또는 연락처를 입력해주세요:\n예: /customer 홍길동")
        return
