# web_service/app/config.py

import os
import logging
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask / Core
    SECRET_KEY = os.getenv("SECRET_KEY")
    MONGODB_URI = os.getenv("MONGODB_URI")
    DB_NAME = os.getenv("DB_NAME", "expTracker").strip()

    # 3rd Party
    EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY", "").strip()
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # Bifrost Auth
    raw_url = os.getenv("BIFROST_URL") or os.getenv("BIFROST_BASE_URL", "")
    BIFROST_URL = raw_url.strip().rstrip('/')
    BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID", "").strip()
    BIFROST_CLIENT_SECRET = os.getenv("BIFROST_CLIENT_SECRET", "").strip()
    BIFROST_WEBHOOK_SECRET = os.environ.get('BIFROST_WEBHOOK_SECRET')

    # Timeouts
    BIFROST_TIMEOUT = 60
    ROLE_LEVELS = {
        'user': 1,
        'premium_user': 2,
        'admin': 99
    }

    @staticmethod
    def validate():
        required_vars = ["MONGODB_URI", "DB_NAME", "BIFROST_URL", "BIFROST_CLIENT_ID"]
        missing = [var for var in required_vars if not getattr(Config, var)]

        if missing:
            logging.critical(f"CONFIG ERROR: Missing {', '.join(missing)}")
        else:
            logging.info(f"✅ Config Loaded. Bifrost: {Config.BIFROST_URL}")