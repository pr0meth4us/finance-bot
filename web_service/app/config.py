# --- web_service/app/config.py (FULL) ---

import os

class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")

    # Mongo
    MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
    DB_NAME = os.getenv("DB_NAME", "expTracker").strip()

    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # Optional: assert basics present (log-only; don’t crash container)
    @staticmethod
    def validate():
        missing = []
        if not Config.MONGODB_URI:
            missing.append("MONGODB_URI")
        if not Config.DB_NAME:
            missing.append("DB_NAME")
        if missing:
            print(f"[Config] Missing env vars: {', '.join(missing)}")
