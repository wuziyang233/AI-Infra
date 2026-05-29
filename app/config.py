import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/sqlite/ai_infra.db")
CHROMA_PATH = os.getenv("CHROMA_PATH", "data/chroma")
REPORT_DIR = os.getenv("REPORT_DIR", "data/reports")
COLLECT_CRON_HOUR = int(os.getenv("COLLECT_CRON_HOUR", "8"))
COLLECT_CRON_MINUTE = int(os.getenv("COLLECT_CRON_MINUTE", "0"))
REPORT_CRON_HOUR = int(os.getenv("REPORT_CRON_HOUR", "9"))
REPORT_CRON_MINUTE = int(os.getenv("REPORT_CRON_MINUTE", "0"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Shanghai")
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")
FEISHU_SECRET = os.getenv("FEISHU_SECRET", "")
WEB_AUTH_USERNAME = os.getenv("WEB_AUTH_USERNAME", "")
WEB_AUTH_PASSWORD = os.getenv("WEB_AUTH_PASSWORD", "")
