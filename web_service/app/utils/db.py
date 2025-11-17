import logging
import certifi
from flask import g, current_app
from pymongo import MongoClient

log = logging.getLogger(__name__)

MONGO_CONNECTION_ARGS = {
    "tls": True,
    "serverSelectionTimeoutMS": 30000,
    "connectTimeoutMS": 20000,
    "socketTimeoutMS": 20000,
    "tlsCAFile": certifi.where(),
}

def get_db_client():
    """Connects to MongoDB using Flask's 'g' context."""
    if 'db_client' not in g:
        uri = current_app.config['MONGODB_URI']
        try:
            g.db_client = MongoClient(uri, **MONGO_CONNECTION_ARGS)
        except Exception as e:
            log.error(f"Failed to create MongoClient: {e}", exc_info=True)
            raise e
    return g.db_client

def get_db():
    """Returns a handle to the specific database."""
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

# --- Collection Accessors ---

def transactions_collection():
    return get_db().transactions

def debts_collection():
    return get_db().debts

def settings_collection():
    return get_db().settings

def reminders_collection():
    return get_db().reminders