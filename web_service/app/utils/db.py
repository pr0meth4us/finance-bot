# web_service/app/utils/db.py
import logging
import certifi
from pymongo import MongoClient, ASCENDING, DESCENDING
from flask import current_app, g

log = logging.getLogger(__name__)

def init_db(app):
    """Initializes the global database connection and indexes."""
    try:
        client = MongoClient(
            app.config['MONGODB_URI'],
            tls=True,
            tlsCAFile=certifi.where(),
            maxPoolSize=50
        )
        app.db = client[app.config['DB_NAME']]
        init_db_indexes(app.db)
        log.info("Successfully connected to MongoDB and initialized indexes.")
    except Exception as e:
        log.error(f"Failed to connect to MongoDB: {e}")
        raise


def get_db():
    """Returns the global database instance."""
    return current_app.db


def init_db_indexes(db):
    """Creates required MongoDB indexes to ensure O(1) read performance and enforce uniqueness."""
    try:
        # Core application indexes
        db.transactions.create_index([("account_id", ASCENDING), ("timestamp", DESCENDING)])
        db.transactions.create_index([("account_id", ASCENDING), ("status", ASCENDING)])

        # UNIQUE index for bank statement imports to prevent duplicate processing.
        # sparse=True allows manually entered transactions without a bank_reference_id to bypass the unique check.
        db.transactions.create_index(
            [("account_id", ASCENDING), ("bank_reference_id", ASCENDING)],
            unique=True,
            sparse=True
        )

        db.debts.create_index([("account_id", ASCENDING), ("status", ASCENDING)])
        db.users.create_index([("account_id", ASCENDING)], unique=True)
        db.settings.create_index([("account_id", ASCENDING)], unique=True)

        log.info("Database indexes verified/created successfully.")
    except Exception as e:
        log.error(f"Error creating database indexes: {e}")

def close_db(e=None):
    """No-op. Global client is managed by the application lifecycle."""
    pass

# --- Collection Accessors ---
def transactions_collection():
    return get_db().transactions


def debts_collection():
    return get_db().debts


def settings_collection():
    return get_db().settings


def reminders_collection():
    return get_db().reminders