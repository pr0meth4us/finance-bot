# --- Start of file: web_service/app/auth/routes.py ---

from flask import Blueprint, request, jsonify
from datetime import datetime
from bson import ObjectId
from app import get_db
from zoneinfo import ZoneInfo
import logging

log = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
UTC_TZ = ZoneInfo("UTC")

# --- ADMIN CONSTANTS REMOVED ---
# All users are now treated equally upon creation.

DEFAULT_EXPENSE_CATEGORIES = [
    "Food", "Drink", "Transport", "Shopping", "Bills", "Utilities",
    "Entertainment", "Personal Care", "Work", "Alcohol", "For Others",
    "Health", "Investment", "Forgot"
]
DEFAULT_INCOME_CATEGORIES = [
    "Salary", "Bonus", "Freelance", "Commission", "Allowance", "Gift",
    "Investment"
]


def get_default_settings_for_user():
    """
    Generates the default user profile document for any new user.
    All users start as 'user' and 'inactive'.
    """
    # No more admin check. Everyone gets the same default document.
    return {
        "name_en": None,
        "name_km": None,
        "role": "user",
        "subscription_status": "inactive",
        "settings": {
            "language": None,
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
        }
    }


def serialize_user(user):
    """Serializes user document for JSON, converting ObjectId."""
    if '_id' in user:
        user['_id'] = str(user['_id'])
    return user


@auth_bp.route('/find_or_create', methods=['POST'])
def find_or_create_user():
    """
    This is the primary authentication endpoint for the bot.
    It finds a user by their telegram_id or creates them if they don't exist.
    Access is gated *only* by subscription_status.
    """
    try:
        db = get_db()
    except Exception as e:
        return jsonify({"error": "Failed to connect to database", "details": str(e)}), 500

    data = request.json
    telegram_user_id = data.get('telegram_user_id')

    if not telegram_user_id:
        return jsonify({"error": "telegram_user_id is required"}), 400

    telegram_user_id = str(telegram_user_id)
    user = None

    try:
        user = db.users.find_one({"telegram_user_id": telegram_user_id})
    except Exception as e:
        return jsonify({"error": "Database query failed", "details": str(e)}), 500

    if not user:
        # Get the standard default profile for a new user
        default_profile = get_default_settings_for_user()

        new_user_doc = {
            "telegram_user_id": telegram_user_id,
            "created_at": datetime.now(UTC_TZ),
            "onboarding_complete": False,
            **default_profile
        }

        try:
            result = db.users.insert_one(new_user_doc)
            user = db.users.find_one({"_id": result.inserted_id})
        except Exception as e:
            return jsonify({"error": "Database insert failed", "details": str(e)}), 500

    if not user:
        return jsonify({"error": "Failed to find or create user"}), 500

    # --- MODIFIED ACCESS CHECK ---
    # We no longer check for 'admin' role. All bot access, for all users,
    # is gated *only* by the subscription_status.
    if user['subscription_status'] != 'active':
        error_msg = (
            "🚫 Subscription not active.\n"
            "🚫 ការជាវ (Subscription) មិនទាន់ដំណើរការទេ។\n\n"
            "សូមទាក់ទង @pr0meth4us ដើម្បីធ្វើការជាវ និងប្រើប្រាស់ Bot នេះ។\n"
            "For subscription info, please contact: @pr0meth4us"
        )
        return jsonify({"error": error_msg}), 403
    # --- END MODIFICATION ---

    return jsonify(serialize_user(user))
# --- End of file ---