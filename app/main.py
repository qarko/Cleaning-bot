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
from app.bot.handlers.reservation import get_reservation_handler, today_command, list_command, view_callback
from app.bot.handlers.task import action_callback, photo_handler, skip_photo_handler, payment_callback, mytasks_command
from app.bot.handlers.quote import quote_command, quote_item_callback, quote_subtype_callback, quote_qty_callback
from app.bot.handlers.customer import customer_command
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

    # 핸들러 등록
    bot_app.add_handler(get_start_handler())
    bot_app.add_handler(get_reservation_handler())
    bot_app.add_handler(CommandHandler("today", today_command))
    bot_app.add_handler(CommandHandler("list", list_command))
    bot_app.add_handler(CommandHandler("mytasks", mytasks_command))
    bot_app.add_handler(CommandHandler("quote", quote_command))
    bot_app.add_handler(CommandHandler("customer", customer_command))

    # 콜백 핸들러 (순서 중요)
    bot_app.add_handler(CallbackQueryHandler(view_callback, pattern=r"^view:"))
    bot_app.add_handler(CallbackQueryHandler(action_callback, pattern=r"^action:"))
    bot_app.add_handler(CallbackQueryHandler(payment_callback, pattern=r"^pay:"))
    bot_app.add_handler(CallbackQueryHandler(quote_item_callback, pattern=r"^item:"))
    bot_app.add_handler(CallbackQueryHandler(quote_subtype_callback, pattern=r"^subtype:"))
    bot_app.add_handler(CallbackQueryHandler(quote_qty_callback, pattern=r"^qty:"))

    # 사진 핸들러 (업무 처리용)
    bot_app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    bot_app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r"^(?!.*\d{2,})"),
        skip_photo_handler,
    ))

    # 봇 시작
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling(drop_pending_updates=True)
    logger.info("Telegram bot started")

    # 스케줄러 (매일 아침 8시 일정 알림)
    scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        lambda: asyncio.create_task(send_daily_schedule(bot_app.bot)),
        trigger=CronTrigger(hour=8, minute=0),
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
            ("carseat", "일반", 40000),
            ("carseat", "가죽", 50000),
            ("carseat", "스웨이드", 55000),
            ("mattress", "싱글", 50000),
            ("mattress", "더블", 60000),
            ("mattress", "퀸", 70000),
            ("mattress", "킹", 80000),
            ("sofa", "패브릭", 80000),
            ("sofa", "가죽", 100000),
            ("sofa", "스웨이드", 110000),
            ("other", "기타", 0),
        ]
        for item_type, subtype, price in defaults:
            db.add(Pricing(item_type=item_type, item_subtype=subtype, price=price, is_active=True))
        await db.commit()
        logger.info("Default pricing seeded")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
