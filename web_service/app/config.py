# --- web_service/app/config.py (FULL) ---

import os

# --- DEBUG TRACING ---
print("--- [Config] Loading Environment Variables ---")
print(f"[Config] MONGODB_URI: {os.getenv('MONGODB_URI', 'NOT SET')[:15]}...")
print(f"[Config] DB_NAME: {os.getenv('DB_NAME', 'NOT SET')}")
print(f"[Config] TELEGRAM_TOKEN: {os.getenv('TELEGRAM_TOKEN', 'NOT SET')[:10]}...")
print(f"[Config] TELEGRAM_CHAT_ID: {os.getenv('TELEGRAM_CHAT_ID', 'NOT SET')}")

# --- NEW: DATA API VARS ---
print(f"[Config] DATA_API_URL: {os.getenv('DATA_API_URL', 'NOT SET')}")
print(f"[Config] DATA_API_KEY: {os.getenv('DATA_API_KEY', 'NOT SET')[:5]}...")
print("----------------------------------------------")
# --- END DEBUG TRACING ---


class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")

    # Mongo
    MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
    DB_NAME = os.getenv("DB_NAME", "expTracker").strip()

    # --- NEW: DATA API Config ---
    # Get this from your Atlas Dashboard -> Data API
    DATA_API_URL = os.getenv("DATA_API_URL", "").strip()
    DATA_API_KEY = os.getenv("DATA_API_KEY", "").strip()
    # --- END NEW ---

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

        # --- NEW: Validate Data API ---
        if not Config.DATA_API_URL:
            missing.append("DATA_API_URL")
        if not Config.DATA_API_KEY:
            missing.append("DATA_API_KEY")
        # --- END NEW ---

        if missing:
            print(f"[Config] Missing env vars: {', '.join(missing)}")