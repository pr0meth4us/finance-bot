import certifi
from flask import Flask, jsonify
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import requests
from web_service.config import Config

def send_daily_reminder_job():
    """Checks if a transaction was logged today and sends a reminder if not."""
    client = MongoClient(Config.MONGODB_URI, tls=True, tlsCAFile=certifi.where())
    db = client[Config.DB_NAME]

    from datetime import datetime, time
    today_start = datetime.combine(datetime.utcnow().date(), time.min)

    count = db.transactions.count_documents({'timestamp': {'$gte': today_start}})

    if count == 0 and Config.TELEGRAM_TOKEN and Config.TELEGRAM_CHAT_ID:
        token = Config.TELEGRAM_TOKEN
        chat_id = Config.TELEGRAM_CHAT_ID
        message = "Hey! 잊지마! (Don't forget!)\n\nLooks like you haven't logged any transactions today. Take a moment to log your activity! ✍️"
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': message}
        try:
            requests.post(url, json=payload)
            print("Sent daily reminder.")
        except Exception as e:
            print(f"Failed to send reminder: {e}")
    else:
        print("Skipped daily reminder, transactions found or config missing.")

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
    app.register_blueprint(settings_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(debts_bp)

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(send_daily_reminder_job, trigger=CronTrigger(hour=21, minute=0))
    scheduler.start()
    print("⏰ Daily reminder job scheduled for 21:00 server time.")

    @app.route("/health")
    def health_check():
        return jsonify({"status": "ok"})

    return app