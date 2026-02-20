# web_service/app/utils/db.py

import logging
from flask import current_app

log = logging.getLogger(__name__)


def get_db():
    """Returns a handle to the specific database using the global client."""
    return current_app.db


def close_db(e=None):
    """No-op. Global client is managed by the application lifecycle."""
    pass


def init_db_indexes(app):
    """Creates essential MongoDB indexes to prevent full collection scans."""
    db = app.db
    try:
        # Settings: Exact match for user lookups
        db.settings.create_index("account_id", unique=True)

        # Transactions: Filtered by account_id, frequently sorted by timestamp
        db.transactions.create_index([("account_id", 1), ("timestamp", -1)])

        # Debts: Filtered by account_id and status
        db.debts.create_index([("account_id", 1), ("status", 1)])

        # Reminders: For the cron job that looks for unsent reminders
        db.reminders.create_index([("status", 1), ("scheduled_for", 1)])

        log.info("✅ Database indexes verified/created successfully.")
    except Exception as e:
        log.error(f"Failed to create database indexes: {e}")


# --- Collection Accessors ---
def transactions_collection():
    return get_db().transactions


def debts_collection():
    return get_db().debts


def settings_collection():
    return get_db().settings


def reminders_collection():
    return get_db().reminders