# --- web_service/app/utils/db.py (Refactored) ---

from flask import g, current_app
from pymongo import MongoClient
import certifi
import logging

log = logging.getLogger(__name__)

MONGO_CONNECTION_ARGS = {
    "tls": True,
    "serverSelectionTimeoutMS": 30000,
    "connectTimeoutMS": 20000,
    "socketTimeoutMS": 20000,
    "tlsCAFile": certifi.where(),
}

def get_db_client():
    """
    Connects to MongoDB.
    Uses Flask's 'g' to reuse the connection per-request.
    """
    if 'db_client' not in g:
        uri = current_app.config['MONGODB_URI']
        try:
            g.db_client = MongoClient(uri, **MONGO_CONNECTION_ARGS)
        except Exception as e:
            log.error(f"Failed to create MongoClient: {e}", exc_info=True)
            raise e
    return g.db_client

def get_db():
    """
    Returns a handle to the specific database.
    """
    if 'db' not in g:
        client = get_db_client()
        g.db = client[current_app.config['DB_NAME']]
    return g.db

def close_db(e=None):
    """Closes the database connection on app context teardown."""
    client = g.pop('db_client', None)
    if client is not None:
        client.close()
        g.pop('db', None)


# --- Collection Definitions ---
# Access collections via these functions to ensure the db connection is live.

def transactions_collection():
    """Returns a handle to the 'transactions' collection."""
    return get_db().transactions

def debts_collection():
    """Returns a handle to the 'debts' collection."""
    return get_db().debts

def settings_collection():
    """
    Returns a handle to the 'settings' collection.
    This collection stores user-specific profiles, settings, and categories.
    """
    return get_db().settings

def reminders_collection():
    """Returns a handle to the 'reminders' collection."""
    return get_db().reminders

# The 'users_collection' from v1 is now obsolete and has been removed.
# User authentication is handled by Bifrost (accounts collection).
# User profiles are stored in the 'settings' collection.