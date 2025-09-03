import certifi
from flask import Flask, jsonify
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import requests
from .config import Config
from datetime import datetime, time, date


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
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': message}
        try:
            requests.post(url, json=payload, timeout=5)
            print("Sent daily transaction reminder.")
        except Exception as e:
            print(f"Failed to send transaction reminder: {e}")
    else:
        print("Skipped daily transaction reminder, transactions found or config missing.")
    client.close()


def send_custom_reminders_job():
    """Checks for and sends scheduled custom reminders for the current day."""
    client = MongoClient(Config.MONGODB_URI, tls=True, tlsCAFile=certifi.where())
    db = client[Config.DB_NAME]

    today = date.today()
    today_start = datetime.combine(today, time.min)
    today_end = datetime.combine(today, time.max)

    query = {'reminder_date': {'$gte': today_start, '$lte': today_end}}
    reminders_to_send = list(db.reminders.find(query))

    if reminders_to_send and Config.TELEGRAM_TOKEN:
        token = Config.TELEGRAM_TOKEN
        url = f"https://api.telegram.org/bot{token}/sendMessage"

        for reminder in reminders_to_send:
            message = f"🔔 Reminder:\n\n{reminder['purpose']}"
            payload = {'chat_id': reminder['chat_id'], 'text': message}
            try:
                requests.post(url, json=payload, timeout=5)
                print(f"Sent custom reminder to {reminder['chat_id']}.")
                # Delete the reminder after sending
                db.reminders.delete_one({'_id': reminder['_id']})
            except Exception as e:
                print(f"Failed to send custom reminder: {e}")
    else:
        print("No custom reminders to send today.")
    client.close()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    client = MongoClient(Config.MONGODB_URI, tls=True, tlsCAFile=certifi.where())
    app.db = client[Config.DB_NAME]
    print("✅ MongoDB connection successful.")

    # Register Blueprints
    from .settings.routes import settings_bp
    from .analytics.routes import analytics_bp
    from .transactions.routes import transactions_bp
    from .debts.routes import debts_bp
    from .summary.routes import summary_bp
    from .reminders.routes import reminders_bp  # New Reminder Blueprint

    app.register_blueprint(settings_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(debts_bp)
    app.register_blueprint(summary_bp)
    app.register_blueprint(reminders_bp)  # Registering the new blueprint

    scheduler = BackgroundScheduler(daemon=True, timezone='Asia/Phnom_Penh')
    # Schedule daily transaction check
    scheduler.add_job(send_daily_reminder_job, trigger=CronTrigger(hour=21, minute=0))
    # Schedule custom reminder check
    scheduler.add_job(send_custom_reminders_job, trigger=CronTrigger(hour=9, minute=0))
    scheduler.start()
    print("⏰ Daily transaction reminder scheduled for 21:00 Phnom Penh time.")
    print("⏰ Custom reminder check scheduled for 09:00 Phnom Penh time.")

    @app.route("/health")
    def health_check():
        return jsonify({"status": "ok"})

    return app