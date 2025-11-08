import os
import certifi
from flask import current_app
from pymongo import MongoClient
from datetime import datetime
from zoneinfo import ZoneInfo
from .config import Config

# Constants
UTC_TZ = ZoneInfo("UTC")

class DB:
    """
    Centralized MongoDB client management for Flask.
    """
    def __init__(self):
        self.client = None
        self.db = None

    def init_app(self, app):
        """Initializes the MongoDB client with Flask app configuration."""
        app.config.from_object(get_config_class())

        # Using certifi for TLS/SSL certificate verification, crucial for cloud MongoDB (e.g., Atlas)
        self.client = MongoClient(app.config['MONGO_URI'], tlsCAFile=certifi.where())
        self.db = self.client[app.config['DATABASE_NAME']]

        print(f"✅ MongoDB client initialized for database: {app.config['DATABASE_NAME']}")

        # Ensure unique index on user_id for the multi-tenant collections
        self.db.users.create_index("telegram_user_id", unique=True)
        self.db.settings.create_index("user_id", unique=True)
        self.db.transactions.create_index("user_id")
        self.db.debts.create_index("user_id")

        # Automatically create or update the super-admin account on startup
        self._ensure_super_admin(app.config['SUPER_ADMIN_ID'])


    def _ensure_super_admin(self, super_admin_id):
        """Creates the initial super-admin account if it doesn't exist."""

        # Admin-Specific Defaults (from requirement 2: Notification IDs)
        default_notification_settings = {
            'reminder_target_chat_id': "-1003192465072",
            'telegram_chat_id': "-4876783109"
        }

        # Initial Balance setting removed from v1 Initial Balance transaction logic
        default_initial_balances = {
            'USD': 0.0,
            'KHR': 0.0
        }

        # Check if the super-admin user exists
        admin_user = self.db.users.find_one({"telegram_user_id": super_admin_id})

        if admin_user:
            # If exists, ensure they still have the correct role/status
            self.db.users.update_one(
                {"_id": admin_user["_id"]},
                {
                    "$set": {
                        "is_admin": True,
                        "subscription_status": "active",
                        "updated_at": datetime.now(UTC_TZ)
                    }
                }
            )
            # Ensure their settings are configured
            self.db.settings.update_one(
                {"user_id": super_admin_id},
                {
                    "$set": {
                        "language": "en",
                        "rate_preference": "live",
                        "initial_balances": default_initial_balances,
                        "notification_ids": default_notification_settings
                    },
                    "$setOnInsert": {
                        "created_at": datetime.now(UTC_TZ),
                        # Default categories will be handled in a later phase to be robust
                        "categories": []
                    }
                },
                upsert=True
            )
            print(f"✅ Super-Admin {super_admin_id} status confirmed.")
        else:
            # Create the super-admin user
            new_user = {
                "telegram_user_id": super_admin_id,
                "subscription_status": "active",
                "is_admin": True,
                "created_at": datetime.now(UTC_TZ),
                "updated_at": datetime.now(UTC_TZ)
            }
            self.db.users.insert_one(new_user)

            # Create the super-admin settings document
            self.db.settings.insert_one({
                "user_id": super_admin_id,
                "language": "en",
                "rate_preference": "live",
                "fixed_usd_khr_rate": 4100.0, # Default fixed rate
                "initial_balances": default_initial_balances,
                "notification_ids": default_notification_settings,
                "categories": [], # Default categories will be handled later
                "created_at": datetime.now(UTC_TZ),
                "updated_at": datetime.now(UTC_TZ)
            })
            print(f"➕ Super-Admin {super_admin_id} created.")


    def get_user_settings(self, user_id):
        """Fetches the settings document for a given user."""
        return self.db.settings.find_one({"user_id": str(user_id)})


# Create a global DB object that Flask extensions often use
db_client = DB()

from .config import get_config_class