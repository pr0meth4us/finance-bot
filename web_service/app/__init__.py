import certifi
from flask import Flask, jsonify
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import requests
from .config import Config
from datetime import datetime, time


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
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    count = db.transactions.count_documents({'timestamp': {'$gte': today_start}})
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