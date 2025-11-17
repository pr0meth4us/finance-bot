import logging
import requests
from flask import Flask, jsonify, current_app
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .config import Config
from app.utils.db import get_db, close_db
from app.jobs import run_scheduled_report, send_daily_reminder_job, send_telegram_message

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Explicitly store config vars in app config for access in blueprints/utils
    app.config['MONGODB_URI'] = Config.MONGODB_URI
    app.config['DB_NAME'] = Config.DB_NAME
    app.config['TELEGRAM_TOKEN'] = Config.TELEGRAM_TOKEN
    app.config['BIFROST_URL'] = Config.BIFROST_URL
    app.config['BIFROST_CLIENT_ID'] = Config.BIFROST_CLIENT_ID
    app.config['BIFROST_CLIENT_SECRET'] = Config.BIFROST_CLIENT_SECRET

    app.teardown_appcontext(close_db)

    # Initialize Scheduler
    scheduler = BackgroundScheduler(daemon=True, timezone='Asia/Phnom_Penh')

    # Daily Reminder (9 PM)
    scheduler.add_job(send_daily_reminder_job, trigger=CronTrigger(hour=21, minute=0), id='daily_reminder',
                      replace_existing=True)

    # Reports
    scheduler.add_job(run_scheduled_report, args=['weekly'], trigger=CronTrigger(day_of_week='mon', hour=8, minute=0),
                      id='weekly_report', replace_existing=True)
    scheduler.add_job(run_scheduled_report, args=['monthly'], trigger=CronTrigger(day=1, hour=8, minute=30),
                      id='monthly_report', replace_existing=True)
    scheduler.add_job(run_scheduled_report, args=['semesterly'],
                      trigger=CronTrigger(month='1,7', day=1, hour=9, minute=0), id='semesterly_report',
                      replace_existing=True)
    scheduler.add_job(run_scheduled_report, args=['yearly'], trigger=CronTrigger(month=1, day=1, hour=9, minute=30),
                      id='yearly_report', replace_existing=True)

    scheduler.start()
    app.scheduler = scheduler

    # Register Blueprints
    from .settings.routes import settings_bp
    from .analytics.routes import analytics_bp
    from .transactions.routes import transactions_bp
    from .debts.routes import debts_bp
    from .summary.routes import summary_bp
    from .reminders.routes import reminders_bp
    from .users.routes import users_bp

    app.register_blueprint(settings_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(debts_bp)
    app.register_blueprint(summary_bp)
    app.register_blueprint(reminders_bp)
    app.register_blueprint(users_bp)

    @app.route("/health")
    def health_check():
        return jsonify({"status": "ok"})

    @app.route("/__egress_ip")
    def egress_ip():
        """Returns public egress IP for debugging."""
        try:
            r = requests.get("https://api.ipify.org?format=json", timeout=5)
            return jsonify(r.json())
        except Exception:
            return jsonify({"error": "Unavailable"}), 502

    @app.route("/__db_ping")
    def db_ping():
        """Diagnostics for DB connection."""
        try:
            db = get_db()
            db.command("ping")
            return jsonify({"ok": True, "db": current_app.config['DB_NAME']})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    return app