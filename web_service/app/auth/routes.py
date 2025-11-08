# --- Start of file: web_service/app/auth/routes.py ---

from flask import Blueprint, request, jsonify
from datetime import datetime
from bson import ObjectId
from app import get_db
from zoneinfo import ZoneInfo

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
UTC_TZ = ZoneInfo("UTC")

# Hardcoded Admin configuration
ADMIN_TELEGRAM_ID = "1836585300"
ADMIN_REMINDER_CHAT_ID = "-1003192465072"
ADMIN_REPORT_CHAT_ID = "-4876783109"

DEFAULT_EXPENSE_CATEGORIES = [
    "Food", "Drink", "Transport", "Shopping", "Bills", "Utilities",
    "Entertainment", "Personal Care", "Work", "Alcohol", "For Others",
    "Health", "Investment", "Forgot"
]
DEFAULT_INCOME_CATEGORIES = [
    "Salary", "Bonus", "Freelance", "Commission", "Allowance", "Gift",
    "Investment"
]


def get_default_settings_for_user(telegram_id):
    """
    Generates the default user profile document.
    Grants admin privileges and chat IDs if the user is the hardcoded admin.
    """
    is_admin = str(telegram_id) == ADMIN_TELEGRAM_ID

    if is_admin:
        return {
            "name": "Admin",
            "role": "admin",
            "subscription_status": "active",
            "settings": {
                "language": "en",
                "rate_preference": "live",
                "fixed_rate": 4100,
                "notification_chat_ids": {
                    "reminder": ADMIN_REMINDER_CHAT_ID,
                    "report": ADMIN_REPORT_CHAT_ID
                },
                "initial_balances": {"USD": 0, "KHR": 0},
                "categories": {
                    "expense": DEFAULT_EXPENSE_CATEGORIES,
                    "income": DEFAULT_INCOME_CATEGORIES
                }
            }
        }

    # Default for a new, non-admin user
    return {
        "name": "New User",
        "role": "user",
        "subscription_status": "inactive",
        "settings": {
            "language": "en",
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
    """
    db = get_db()
    data = request.json
    telegram_user_id = data.get('telegram_user_id')

    if not telegram_user_id:
        return jsonify({"error": "telegram_user_id is required"}), 400

    telegram_user_id = str(telegram_user_id)

    user = db.users.find_one({"telegram_user_id": telegram_user_id})

    if not user:
        # User doesn't exist, create them
        default_profile = get_default_settings_for_user(telegram_user_id)

        new_user_doc = {
            "telegram_user_id": telegram_user_id,
            "created_at": datetime.now(UTC_TZ),
            "onboarding_complete": False,  # <-- THIS IS THE FIX
            **default_profile
        }

        result = db.users.insert_one(new_user_doc)
        user = db.users.find_one({"_id": result.inserted_id})
        # REMOVED: user['is_new_user'] = True (this was the bug)

    if not user:
        return jsonify({"error": "Failed to find or create user"}), 500

    if user['role'] != 'admin' and user['subscription_status'] != 'active':
        return jsonify({
            "error": "Subscription not active. Please subscribe to use this bot."
        }), 403

    return jsonify(serialize_user(user))

# --- End of file ---