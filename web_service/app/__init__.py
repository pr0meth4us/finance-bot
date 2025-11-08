# --- Start of refactored file: web_service/app/__init__.py ---
import io
import requests
from flask import Flask, jsonify
from pymongo.errors import ConnectionFailure
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, time, timedelta, date
from zoneinfo import ZoneInfo
from bson import ObjectId

# Import new modules
from .config import get_config_class
from .db import db_client
# Note: The original file had a lot of local imports and helper functions here.
# They are better moved to their respective blueprint files for modularity.

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")

def create_app():
    app = Flask(__name__)
    config_class = get_config_class()
    app.config.from_object(config_class)

    # 1. Initialize DB client
    try:
        db_client.init_app(app)
    except ConnectionFailure as e:
        print(f"FATAL: MongoDB Connection Failed: {e}")
        # In production, you might want to stop the app, but for dev, we print and continue.

    app.db = db_client.db # Expose the db connection via the app context for blueprints

    # 2. Register Blueprints (Assuming a clean structure: auth, transactions, debts, summary, analytics)

    # Import Blueprints
    from .auth.routes import auth_bp
    from .transactions.routes import transactions_bp # Assuming this exists
    from .debts.routes import debts_bp             # Assuming this exists
    from .summary.routes import summary_bp           # Assuming this exists
    from .analytics.routes import analytics_bp         # Assuming this exists
    from .settings.routes import settings_bp           # Assuming this exists

    app.register_blueprint(auth_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(debts_bp)
    app.register_blueprint(summary_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(settings_bp)

    # 3. Remove single-user scheduler and initialize global scheduler
    # NOTE: The original scheduler logic is removed here as it was single-tenant.
    # The new, multi-tenant scheduler logic will be implemented in a dedicated module
    # (e.g., `app.reminders.jobs`) in a later phase.

    # def start_scheduler():
    #     scheduler = BackgroundScheduler(daemon=True)
    #     ... (OLD CODE REMOVED) ...
    #     scheduler.start()

    # start_scheduler() # Commented out until multi-tenant logic is implemented

    @app.route('/healthz')
    def health_check():
        """Basic health check endpoint."""
        try:
            # Check MongoDB connection
            db_client.client.admin.command('ping')
            mongo_status = "ok"
        except Exception:
            mongo_status = "error"

        return jsonify({"status": "ok", "database": mongo_status}), 200

    return app

# --- End of refactored file: web_service/app/__init__.py ---