# web_service/app/__init__.py

import certifi
from flask import Flask, jsonify, current_app
from flask_cors import CORS
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flasgger import Swagger
from .config import Config
from .services.scheduler import send_daily_reminder_job, run_scheduled_report


def get_db(app=None):
    if app is not None:
        return app.db
    return current_app.db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # --- CORS CONFIG (Updated) ---
    CORS(app, supports_credentials=True, resources={
        r"/*": {
            "origins": [
                "https://savvify-web.vercel.app",
                "http://localhost:3000"
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    client = MongoClient(Config.MONGODB_URI, tls=True, tlsCAFile=certifi.where())
    app.db = client[Config.DB_NAME]

    scheduler = BackgroundScheduler(daemon=True, timezone='Asia/Phnom_Penh')

    scheduler.add_job(
        send_daily_reminder_job,
        trigger=CronTrigger(hour=21, minute=0),
        id='daily_reminder',
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_report,
        args=['weekly'],
        trigger=CronTrigger(day_of_week='mon', hour=8, minute=0),
        id='weekly_report',
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_report,
        args=['monthly'],
        trigger=CronTrigger(day=1, hour=8, minute=30),
        id='monthly_report',
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_report,
        args=['semesterly'],
        trigger=CronTrigger(month='1,7', day=1, hour=9, minute=0),
        id='semesterly_report',
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_report,
        args=['yearly'],
        trigger=CronTrigger(month=1, day=1, hour=9, minute=30),
        id='yearly_report',
        replace_existing=True,
    )

    scheduler.start()
    app.scheduler = scheduler

    # Register Blueprints
    from .settings.routes import settings_bp
    from .analytics.routes import analytics_bp
    from .transactions.routes import transactions_bp
    from .debts.routes import debts_bp
    from .summary.routes import summary_bp
    from .reminders.routes import reminders_bp
    from .auth.routes import auth_bp
    from .users.routes import users_bp
    from .payments.routes import payments_bp

    app.register_blueprint(settings_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(debts_bp)
    app.register_blueprint(summary_bp)
    app.register_blueprint(reminders_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(payments_bp)

    Swagger(app, template_file='../swagger.yaml')

    @app.route("/health")
    def health_check():
        return jsonify({"status": "ok"})

    return app