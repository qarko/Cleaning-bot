import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import BOT_TOKEN
from app.database import init_db
from app.bot.handlers.start import get_start_handler
from app.bot.handlers.reservation import get_reservation_handler, today_command, tomorrow_command, list_command, view_callback
from app.bot.handlers.task import action_callback, photo_handler, skip_photo_handler, payment_callback, delivery_date_callback, mytasks_command
from app.bot.handlers.quote import quote_command, quote_item_callback, quote_subtype_callback, quote_method_callback, quote_qty_callback
from app.bot.handlers.customer import customer_command
from app.bot.handlers.menu import menu_handler
from app.bot.notifications import send_daily_schedule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot_app: Application = None
scheduler: AsyncIOScheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_app, scheduler

    # DB 초기화
    await init_db()
    logger.info("Database initialized")

    # 기본 가격 데이터 삽입
    await seed_pricing()

    # 텔레그램 봇 설정
    bot_app = Application.builder().token(BOT_TOKEN).build()

    # 핸들러 등록 (순서 중요: ConversationHandler가 먼저)
    bot_app.add_handler(get_start_handler())
    bot_app.add_handler(get_reservation_handler())
    bot_app.add_handler(CommandHandler("today", today_command))
    bot_app.add_handler(CommandHandler("tomorrow", tomorrow_command))
    bot_app.add_handler(CommandHandler("list", list_command))
    bot_app.add_handler(CommandHandler("mytasks", mytasks_command))
    bot_app.add_handler(CommandHandler("quote", quote_command))
    bot_app.add_handler(CommandHandler("customer", customer_command))

    # 콜백 핸들러 (견적은 q_ 접두사로 구분)
    bot_app.add_handler(CallbackQueryHandler(view_callback, pattern=r"^view:"))
    bot_app.add_handler(CallbackQueryHandler(delivery_date_callback, pattern=r"^date"))  # 배송 예정일 (pending_action 체크)
    bot_app.add_handler(CallbackQueryHandler(action_callback, pattern=r"^action:"))
    bot_app.add_handler(CallbackQueryHandler(payment_callback, pattern=r"^pay:"))
    bot_app.add_handler(CallbackQueryHandler(quote_item_callback, pattern=r"^q_item:"))
    bot_app.add_handler(CallbackQueryHandler(quote_subtype_callback, pattern=r"^q_sub:"))
    bot_app.add_handler(CallbackQueryHandler(quote_method_callback, pattern=r"^q_method:"))
    bot_app.add_handler(CallbackQueryHandler(quote_qty_callback, pattern=r"^q_qty:"))

    # 메뉴 버튼 핸들러 (📋 새 예약은 ConversationHandler에서 처리)
    bot_app.add_handler(MessageHandler(
        filters.Regex(r"^(📅 오늘 예약|📆 내일 예약|📝 전체 예약|📌 할 일|💰 견적 계산|👤 고객 조회)$"),
        menu_handler,
    ))

    # 사진 핸들러 (업무 처리 - 사진 업로드 대기 중일 때만)
    bot_app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    # 사진 건너뛰기 핸들러 - pending_action이 있을 때만 동작하므로 안전
    bot_app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        skip_photo_handler,
    ), group=1)  # group=1로 분리하여 ConversationHandler와 충돌 방지

    # 글로벌 에러 핸들러
    async def error_handler(update, context):
        logger.error(f"Bot error: {context.error}", exc_info=context.error)
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "처리 중 오류가 발생했습니다. 다시 시도해주세요."
                )
            except Exception:
                pass

    bot_app.add_error_handler(error_handler)

    # 봇 시작
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling(drop_pending_updates=True)
    logger.info("Telegram bot started")

    # 봇 명령어 목록 설정
    from telegram import BotCommand
    await bot_app.bot.set_my_commands([
        BotCommand("start", "시작 / 메뉴"),
        BotCommand("new", "새 예약 등록"),
        BotCommand("today", "오늘 예약"),
        BotCommand("tomorrow", "내일 예약"),
        BotCommand("list", "전체 예약"),
        BotCommand("mytasks", "내 할 일"),
        BotCommand("quote", "견적 계산"),
        BotCommand("cancel", "예약 등록 취소"),
    ])

    # 스케줄러 (매일 아침 9시 일정 알림)
    scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        lambda: asyncio.create_task(send_daily_schedule(bot_app.bot)),
        trigger=CronTrigger(hour=9, minute=0),
        id="daily_schedule",
    )
    scheduler.start()
    logger.info("Scheduler started")

    yield

    # 종료
    scheduler.shutdown()
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()
    logger.info("Bot stopped")


app = FastAPI(title="Cleaning Business Bot", lifespan=lifespan)

# API 라우터
from app.api.routes.dashboard import router as dashboard_router
app.include_router(dashboard_router)

# 랜딩 페이지 (정적 파일)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 미니앱 프론트엔드
miniapp_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(miniapp_dir):
    app.mount("/app", StaticFiles(directory=miniapp_dir, html=True), name="miniapp")


@app.get("/")
async def landing():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok"}


async def seed_pricing():
    """기본 가격 데이터 삽입"""
    from app.database import async_session
    from app.models.pricing import Pricing
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(Pricing).limit(1))
        if result.scalar_one_or_none():
            return  # 이미 데이터 있음

        defaults = [
            # 카시트 전제품 동일가
            ("carseat", "전제품", 40000),
            # 유모차/웨건
            ("stroller", "쌍둥이유모차", 50000),
            ("wagon", "웨건", 50000),
            # 매트리스 (건식/습식 동일가)
            ("mattress", "싱글", 40000),
            ("mattress", "더블", 45000),
            ("mattress", "퀸", 50000),
            ("mattress", "킹", 60000),
            # 소파 (건식/습식 동일가)
            ("sofa", "2인", 40000),
            ("sofa", "3인", 50000),
            ("sofa", "4인", 60000),
            ("sofa", "5인", 70000),
            # 아기띠
            ("carrier", "단독", 20000),
            ("carrier", "카시트/유모차 동시", 10000),
        ]
        for item_type, subtype, price in defaults:
            db.add(Pricing(item_type=item_type, item_subtype=subtype, price=price, is_active=True))
        await db.commit()
        logger.info("Default pricing seeded")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, loop="asyncio")
