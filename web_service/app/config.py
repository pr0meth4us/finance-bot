import os
import logging


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    MONGODB_URI = os.getenv("MONGODB_URI")
    DB_NAME = os.getenv("DB_NAME", "expTracker").strip()
    EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY", "").strip()
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    BIFROST_WEBHOOK_SECRET = os.environ.get('BIFROST_WEBHOOK_SECRET')

    # Bifrost Auth
    # Support both naming conventions, preferring BIFROST_URL
    # AGGRESSIVELY STRIP WHITESPACE
    raw_url = os.getenv("BIFROST_URL") or os.getenv("BIFROST_BASE_URL", "")
    BIFROST_URL = raw_url.strip().rstrip('/')

    BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID", "").strip()
    BIFROST_CLIENT_SECRET = os.getenv("BIFROST_CLIENT_SECRET", "").strip()

    @staticmethod
    def validate():
        required_vars = [
            "MONGODB_URI",
            "DB_NAME",
            "BIFROST_URL",
            "BIFROST_CLIENT_ID",
            "BIFROST_CLIENT_SECRET"
        ]

        missing = [var for var in required_vars if not getattr(Config, var)]

        if missing:
            logging.critical(f"######## CONFIG ERROR: Missing env vars: {', '.join(missing)} ########")
        else:
            # Log the ID being used (masked secret) to help debug mismatches
            cid = Config.BIFROST_CLIENT_ID
            logging.info(f"✅ Config Loaded. Bifrost Client ID: '{cid}' (Length: {len(cid)})")