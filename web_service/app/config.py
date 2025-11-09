# --- web_service/app/config.py (FULL) ---

import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
    DB_NAME = os.getenv("DB_NAME", "expTracker").strip()
    EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY", "").strip()
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    @staticmethod
    def validate():
        missing = []
        if not Config.MONGODB_URI:
            missing.append("MONGODB_URI")
        if not Config.DB_NAME:
            missing.append("DB_NAME")
        if not Config.EXCHANGERATE_API_KEY:
            missing.append("EXCHANGERATE_API_KEY")
        if missing:
            print(f"[Config] Missing env vars: {', '.join(missing)}")