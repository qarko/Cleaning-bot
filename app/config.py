import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "")
# GROUP_CHAT_ID 미사용 - DM 방식으로 알림 발송
BOSS_INVITE_CODE = os.getenv("BOSS_INVITE_CODE", "BOSS2026")

# 동기 URL (alembic용)
SYNC_DATABASE_URL = DATABASE_URL.replace("asyncpg", "psycopg2") if DATABASE_URL else ""
