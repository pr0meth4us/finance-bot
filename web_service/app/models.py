# web_service/app/models.py

from datetime import datetime
from zoneinfo import ZoneInfo
from bson import ObjectId
from flask import current_app
from app.utils.db import settings_collection

UTC_TZ = ZoneInfo("UTC")

DEFAULT_EXPENSE_CATEGORIES = [
    "Food", "Drink", "Transport", "Shopping", "Bills", "Utilities",
    "Entertainment", "Personal Care", "Work", "Alcohol", "For Others",
    "Health", "Investment", "Forgot", "Rent", "Subscriptions", "Insurance",
    "Education", "Gifts", "Donations", "Family", "Travel", "Pets",
    "Electronics", "Car Maintenance"
]

DEFAULT_INCOME_CATEGORIES = [
    "Salary", "Bonus", "Freelance", "Commission", "Allowance", "Gift",
    "Investment Income", "Other Income"
]


class User:
    def __init__(self, doc):
        self.doc = doc
        self.account_id = doc.get('account_id')
        self.settings = doc.get('settings', {})
        self._id = doc.get('_id')

    @staticmethod
    def get_by_account_id(account_id):
        """
        Retrieves a user profile by Bifrost account_id.
        """
        if isinstance(account_id, str):
            account_id = ObjectId(account_id)

        doc = settings_collection().find_one({"account_id": account_id})
        if doc:
            return User(doc)
        return None

    @staticmethod
    def create(account_id, role='user'):
        """
        Creates a new local user profile linked to a Bifrost account_id.
        """
        if isinstance(account_id, str):
            account_id = ObjectId(account_id)

        current_app.logger.info(f"Provisioning new local profile for account_id: {account_id}")

        new_profile = {
            "account_id": account_id,
            "settings": {
                "language": "en",
                "currency_mode": None,
                "primary_currency": None,
                "rate_preference": "live",
                "fixed_rate": 4100,
                "notification_chat_ids": {
                    "reminder": None,
                    "report": None
                },
                "initial_balances": {"USD": 0, "KHR": 0},
                "categories": {
                    "expense": DEFAULT_EXPENSE_CATEGORIES,
                    "income": DEFAULT_INCOME_CATEGORIES
                }
            },
            "onboarding_complete": False,
            "created_at": datetime.now(UTC_TZ),
            # Store the role locally if needed for quick lookups,
            # though usually we trust the JWT from Bifrost.
            "role": role
        }

        result = settings_collection().insert_one(new_profile)
        new_profile['_id'] = result.inserted_id
        return User(new_profile)

    def update_role(self, new_role):
        """Updates the cached role in the local profile."""
        settings_collection().update_one(
            {"_id": self._id},
            {"$set": {"role": new_role}}
        )