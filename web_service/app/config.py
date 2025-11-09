# --- web_service/app/config.py (FULL) ---

import os

class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")

    # Mongo
    MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
    DB_NAME = os.getenv("DB_NAME", "expTracker").strip()

    # DATA API Config
    DATA_API_URL = os.getenv("DATA_API_URL", "").strip()
    DATA_API_KEY = os.getenv("DATA_API_KEY", "").strip()

    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    @staticmethod
    def validate():
        missing = []
        if not Config.MONGODB_URI:
            missing.append("MONGODB_URI")
        if not Config.DB_NAME:
            missing.append("DB_NAME")
        if not Config.DATA_API_URL:
            missing.append("DATA_API_URL")
        if not Config.DATA_API_KEY:
            missing.append("DATA_API_KEY")

        if missing:
            print(f"[Config] Missing env vars: {', '.join(missing)}")