from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Blueprint, jsonify, g, current_app
from bson import ObjectId
from pymongo import ReturnDocument

from app.utils.db import settings_collection
from app.utils.auth import auth_required
from app.utils.serializers import serialize_profile

users_bp = Blueprint('users', __name__, url_prefix='/users')
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


def _get_default_settings(account_id_obj):
    """Generates the default user profile document."""
    return {
        "account_id": account_id_obj,
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
        "created_at": datetime.now(UTC_TZ)
    }


@users_bp.route('/me', methods=['GET'])
@auth_required(min_role="user")
def get_my_profile():
    """
    Finds or creates the user's profile in the settings collection.
    Returns the profile document and the user's role.
    """
    try:
        account_id = ObjectId(g.account_id)
    except Exception:
        return jsonify({'error': 'Invalid account_id format'}), 400

    user_role = g.role

    # Atomically find or create the profile
    user_profile = settings_collection().find_one_and_update(
        {'account_id': account_id},
        {'$setOnInsert': _get_default_settings(account_id)},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )

    if not user_profile:
        current_app.logger.error(f"Failed to find or create profile for {account_id}")
        return jsonify({"error": "Failed to find or create user profile"}), 500

    return jsonify({
        "profile": serialize_profile(user_profile),
        "role": user_role
    }), 200