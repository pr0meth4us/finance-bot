import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
    DB_NAME = os.getenv("DB_NAME", "expTracker").strip()
    EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY", "").strip()
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # Bifrost Auth
    BIFROST_URL = os.getenv("BIFROST_BASE_URL", "").strip()
    BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID", "").strip()
    BIFROST_CLIENT_SECRET = os.getenv("BIFROST_CLIENT_SECRET", "").strip()

    @staticmethod
    def validate():
        required_vars = [
            "MONGODB_URI",
            "DB_NAME",
            "EXCHANGERATE_API_KEY"
        ]

        missing = [var for var in required_vars if not getattr(Config, var)]

        if missing:
            print(f"[Config] Missing env vars: {', '.join(missing)}")