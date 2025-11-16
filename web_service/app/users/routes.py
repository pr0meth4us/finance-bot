# --- web_service/app/users/routes.py (Fixed) ---
"""
Handles user profile management, replacing the old auth blueprint.
"""
from flask import Blueprint, jsonify, g, current_app
from datetime import datetime
from pymongo import ReturnDocument
from app.utils.db import settings_collection
from app.utils.auth import auth_required
# --- THIS IS THE FIX ---
from app.utils.serializers import serialize_profile  # Import the shared serializer
# --- END FIX ---
from zoneinfo import ZoneInfo
from bson import ObjectId

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


# --- THIS IS THE FIX ---
# Removed telegram_id from the function arguments
def _get_default_settings(account_id_obj: ObjectId):
    # --- END FIX ---
    """
    Generates the default user profile document to be inserted into the
    'settings' collection for a new user.
    """
    # --- THIS IS THE FIX ---
    # The hardcoded check is removed, as requested by the user.
    # All users now get the same default 'None' for chat IDs.
    reminder_chat_id = None
    report_chat_id = None
    # --- END FIX ---

    return {
        "account_id": account_id_obj,
        "settings": {
            "language": "en",  # Default to English
            "currency_mode": None,  # User must set this
            "primary_currency": None,  # User must set this
            "rate_preference": "live",
            "fixed_rate": 4100,
            "notification_chat_ids": {
                "reminder": reminder_chat_id,
                "report": report_chat_id
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


# --- THIS IS THE FIX ---
# This function is now imported from app.utils.serializers
# def serialize_profile(doc): ...
# --- END FIX ---


@users_bp.route('/me', methods=['GET'])
@auth_required(min_role="user")
def get_my_profile():
    """
    This is the new "find_or_create_user" endpoint.
    It's protected by auth_required, which populates g.account_id and g.role.

    It finds the user's profile in the 'settings' collection.
    If not found, it creates one (upsert=True).

    It returns the user's profile document AND their role from Bifrost.
    """
    try:
        try:
            account_id_str = g.account_id
            account_id_obj = ObjectId(account_id_str)
        except Exception:
            return jsonify({'error': 'Invalid account_id format from token'}), 400

        user_role = g.role

        # --- THIS IS THE FIX ---
        if not account_id_obj:
            # --- END FIX ---
            # This should not happen if @auth_required is working
            return jsonify({"error": "Auth decorator failed to provide IDs"}), 500

        db_settings = settings_collection()

        # Atomically find or create the user's settings profile
        user_profile = db_settings.find_one_and_update(
            {'account_id': account_id_obj},
            {
                # --- THIS IS THE FIX ---
                # Pass only the account_id
                '$setOnInsert': _get_default_settings(account_id_obj)
                # --- END FIX ---
            },
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

        if not user_profile:
            current_app.logger.error(f"Failed to find or create profile for {account_id_obj}")
            return jsonify({"error": "Failed to find or create user profile"}), 500

        # The /settings/ GET endpoint expects the root doc
        # but the /users/me endpoint (called by decorator) expects { "profile": {...}, "role": "..." }
        return jsonify({
            "profile": serialize_profile(user_profile),  # Use the imported serializer
            "role": user_role
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error in /users/me: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500