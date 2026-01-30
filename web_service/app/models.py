from datetime import datetime
from zoneinfo import ZoneInfo
from bson import ObjectId
from flask import current_app
from app.utils.db import settings_collection

UTC_TZ = ZoneInfo("UTC")

DEFAULT_EXPENSE_CATEGORIES = [
    "Food", "Drink", "Transport", "Shopping", "Bills", "Utilities", "Entertainment",
    "Personal Care", "Work", "Alcohol", "For Others", "Health", "Investment",
    "Forgot", "Rent", "Subscriptions", "Insurance", "Education", "Gifts",
    "Donations", "Family", "Travel", "Pets", "Electronics", "Car Maintenance"
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
        self.username = doc.get('username')
        self.email = doc.get('email')
        self.display_name = doc.get('display_name')
        self.telegram_id = doc.get('telegram_id')

    @staticmethod
    def get_by_account_id(account_id):
        """Retrieves a user profile by Bifrost account_id."""
        if isinstance(account_id, str):
            account_id = ObjectId(account_id)

        doc = settings_collection().find_one({"account_id": account_id})
        if doc:
            return User(doc)
        return None

    @staticmethod
    def find_by_email(email):
        """Retrieves a user profile by email."""
        doc = settings_collection().find_one({"email": email})
        if doc:
            return User(doc)
        return None

    @staticmethod
    def find_by_telegram_id(telegram_id):
        """Retrieves a user profile by Telegram ID."""
        doc = settings_collection().find_one({"telegram_id": str(telegram_id)})
        if doc:
            return User(doc)
        return None

    @staticmethod
    def create(account_id, role='user', username=None, email=None, display_name=None, telegram_id=None):
        """Creates a new local profile linked to a Bifrost account_id."""
        if isinstance(account_id, str):
            account_id = ObjectId(account_id)

        current_app.logger.info(f"Provisioning new local profile for account_id: {account_id}")

        new_profile = {
            "account_id": account_id,
            "username": username,
            "email": email,
            "display_name": display_name,
            "telegram_id": str(telegram_id) if telegram_id else None,
            "settings": {
                "language": "en",
                "currency_mode": None,
                "primary_currency": None,
                "rate_preference": "live",
                "fixed_rate": 4100,
                "notification_chat_ids": {
                    "reminder": str(telegram_id) if telegram_id else None,
                    "report": str(telegram_id) if telegram_id else None
                },
                "initial_balances": {"USD": 0, "KHR": 0},
                "categories": {
                    "expense": DEFAULT_EXPENSE_CATEGORIES,
                    "income": DEFAULT_INCOME_CATEGORIES
                }
            },
            "onboarding_complete": False,
            "created_at": datetime.now(UTC_TZ),
            "role": role
        }

        result = settings_collection().insert_one(new_profile)
        new_profile['_id'] = result.inserted_id
        return User(new_profile)

    @staticmethod
    def create_from_telegram(telegram_id, display_name):
        """Helper to create a user when we only have a Telegram ID."""
        fake_account_id = ObjectId()
        return User.create(fake_account_id, role='user', display_name=display_name, telegram_id=telegram_id)

    @staticmethod
    def create_from_email(email, password_hash_ignored):
        """Stub for legacy email registration."""
        fake_account_id = ObjectId()
        return User.create(fake_account_id, role='user', email=email)

    @staticmethod
    def verify_password(user, password):
        """Stub. Finance service does not verify passwords locally."""
        return False

    def update_role(self, new_role):
        """Updates the cached role in the local profile."""
        settings_collection().update_one(
            {"_id": self._id},
            {"$set": {"role": new_role}}
        )

    def update_identity(self, username=None, email=None, display_name=None, role=None, telegram_id=None):
        """Syncs identity information from Bifrost to the local profile."""
        updates = {}
        if username: updates["username"] = username
        if email: updates["email"] = email
        if display_name: updates["display_name"] = display_name
        if role: updates["role"] = role
        if telegram_id: updates["telegram_id"] = str(telegram_id)

        if updates:
            settings_collection().update_one(
                {"_id": self._id},
                {"$set": updates}
            )