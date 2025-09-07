# --- Start of modified file: web_service/app/__init__.py ---

import certifi
from flask import Flask, jsonify
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import requests
from .config import Config
from datetime import datetime, time
# --- MODIFICATION START ---
# Import ZoneInfo for timezone-aware calculations in the scheduled job
from zoneinfo import ZoneInfo
# --- MODIFICATION END ---


def send_telegram_message(chat_id, text, token):
    """A simple function to send a message via the Telegram API, callable by APScheduler."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try:
        requests.post(url, json=payload, timeout=10)
        print(f"Sent scheduled message to {chat_id}.")
    except Exception as e:
        print(f"Failed to send scheduled message to {chat_id}: {e}")


def send_daily_reminder_job():
    """Checks if a transaction was logged today and sends a reminder if not."""
    client = MongoClient(Config.MONGODB_URI, tls=True, tlsCAFile=certifi.where())
    db = client[Config.DB_NAME]

    # --- MODIFICATION START ---
    # Calculate "today" based on the local timezone (Asia/Phnom_Penh) to ensure accurate checking.
    # The database stores time in UTC, so we calculate the start of the day in local time,
    # then convert that instant to UTC for the query.

    # 1. Define the local timezone.
    local_tz = ZoneInfo("Asia/Phnom_Penh")

    # 2. Get the current time in the local timezone to determine today's date correctly.
    now_in_phnom_penh = datetime.now(local_tz)

    # 3. Calculate the start of the day in local time (e.g., Sep 8th, 00:00:00+07:00).
    # We create an aware datetime object representing midnight locally.
    today_start_local_aware = datetime.combine(now_in_phnom_penh.date(), time.min, tzinfo=local_tz)

    # 4. Convert the local start time to UTC for querying the database.
    today_start_utc = today_start_local_aware.astimezone(ZoneInfo("UTC"))

    # Original code:
    # today_start = datetime.combine(datetime.utcnow().date(), time.min)
    # count = db.transactions.count_documents({'timestamp': {'$gte': today_start}})

    # Corrected query using UTC start time derived from local date:
    count = db.transactions.count_documents({'timestamp': {'$gte': today_start_utc}})
    # --- MODIFICATION END ---

    if count == 0 and Config.TELEGRAM_TOKEN and Config.TELEGRAM_CHAT_ID:
        token = Config.TELEGRAM_TOKEN
        chat_id = Config.TELEGRAM_CHAT_ID
        message = "Hey! 잊지마! (Don't forget!)\n\nLooks like you haven't logged any transactions today. Take a moment to log your activity! ✍️"
        send_telegram_message(chat_id, message, token)
        print("Sent daily transaction reminder.")
    else:
        print("Skipped daily transaction reminder, transactions found or config missing.")
    client.close()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    client = MongoClient(Config.MONGODB_URI, tls=True, tlsCAFile=certifi.where())
    app.db = client[Config.DB_NAME]
    print("✅ MongoDB connection successful.")

    # Initialize and start the scheduler
    scheduler = BackgroundScheduler(daemon=True, timezone='Asia/Phnom_Penh')
    scheduler.add_job(send_daily_reminder_job, trigger=CronTrigger(hour=21, minute=0))
    scheduler.start()
    app.scheduler = scheduler  # Attach scheduler to the app context
    print("⏰ Daily transaction reminder scheduled for 21:00 Phnom Penh time.")
    print("⏰ Scheduler started for dynamic job scheduling.")

    # Register Blueprints
    from .settings.routes import settings_bp
    from .analytics.routes import analytics_bp
    from .transactions.routes import transactions_bp
    from .debts.routes import debts_bp
    from .summary.routes import summary_bp
    from .reminders.routes import reminders_bp

    app.register_blueprint(settings_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(debts_bp)
    app.register_blueprint(summary_bp)
    app.register_blueprint(reminders_bp)

    @app.route("/health")
    def health_check():
        return jsonify({"status": "ok"})

    return app
# --- End of modified file: web_service/app/__init__.py ---