from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from sqlalchemy import select
from app.database import async_session
from app.models.employee import Employee
from app.bot.keyboards import role_keyboard
from app.config import BOSS_INVITE_CODE

WAITING_INVITE_CODE = 1


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    async with async_session() as db:
        result = await db.execute(select(Employee).where(Employee.telegram_user_id == user_id))
        employee = result.scalar_one_or_none()

    if employee:
        role_label = "사장" if employee.role == "boss" else "직원"
        await update.message.reply_text(
            f"안녕하세요, {employee.name}님! ({role_label})\n\n"
            "📋 /new - 새 예약 등록\n"
            "📅 /today - 오늘 예약\n"
            "📝 /list - 전체 예약\n"
            "💰 /quote - 견적 계산\n"
            "👤 /customer - 고객 조회\n"
            "📌 /mytasks - 내 할 일"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "환영합니다! 역할을 선택해주세요.",
        reply_markup=role_keyboard(),
    )
    return ConversationHandler.END


async def role_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    role = query.data.split(":")[1]

    if role == "boss":
        context.user_data["pending_role"] = "boss"
        await query.edit_message_text("사장 인증 코드를 입력해주세요:")
        return WAITING_INVITE_CODE
    else:
        context.user_data["pending_role"] = "staff"
        await query.edit_message_text("직원 초대 코드를 입력해주세요:")
        return WAITING_INVITE_CODE


async def invite_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    role = context.user_data.get("pending_role", "staff")

    if role == "boss" and code != BOSS_INVITE_CODE:
        await update.message.reply_text("인증 코드가 올바르지 않습니다. 다시 입력해주세요:")
        return WAITING_INVITE_CODE

    if role == "staff" and code != BOSS_INVITE_CODE:
        await update.message.reply_text("초대 코드가 올바르지 않습니다. 다시 입력해주세요:")
        return WAITING_INVITE_CODE

    user = update.effective_user
    name = user.full_name or user.first_name or "Unknown"

    async with async_session() as db:
        employee = Employee(
            name=name,
            telegram_user_id=user.id,
            role=role,
        )
        db.add(employee)
        await db.commit()

    role_label = "사장" if role == "boss" else "직원"
    await update.message.reply_text(
        f"등록 완료! {name}님 ({role_label})\n\n"
        "📋 /new - 새 예약 등록\n"
        "📅 /today - 오늘 예약\n"
        "📝 /list - 전체 예약\n"
        "💰 /quote - 견적 계산\n"
        "👤 /customer - 고객 조회\n"
        "📌 /mytasks - 내 할 일"
    )
    return ConversationHandler.END


def get_start_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
            CallbackQueryHandler(role_callback, pattern=r"^role:"),
        ],
        states={
            WAITING_INVITE_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, invite_code_handler),
            ],
        },
        fallbacks=[CommandHandler("start", start_command)],
    )
