from flask import Blueprint, request, jsonify
from datetime import datetime
from bson import ObjectId
from app import get_db
from zoneinfo import ZoneInfo
from app.utils.auth import get_user_id_from_request  # Ensure this import is present
import logging

log = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
UTC_TZ = ZoneInfo("UTC")

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
    All users start as 'inactive'.
    """
    return {
        "name_en": None,
        "name_km": None,
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
    Finds a user by their telegram_id or creates them if they don't exist.
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

    if user.get('subscription_status') != 'active':
        error_msg = (
            "🚫 Subscription not active.\n"
            "Please contact support to activate your account."
        )
        return jsonify({"error": error_msg}), 403

    return jsonify(serialize_user(user))


# --- NEW ENDPOINTS START HERE ---

@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    """
    Returns the profile of the currently authenticated user.
    Used by the frontend AuthGuard to check for missing email.
    """
    db = get_db()
    user_id, error = get_user_id_from_request()
    if error: return error

    user = db.users.find_one({"_id": user_id})
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify(serialize_user(user))


@auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    """
    Updates the user's profile (specifically email for onboarding).
    """
    db = get_db()
    user_id, error = get_user_id_from_request()
    if error: return error

    data = request.json
    updates = {}

    if 'email' in data:
        updates['email'] = data['email']

    # Add other fields here as needed (e.g., name updates)

    if not updates:
        return jsonify({"error": "No fields to update"}), 400

    db.users.update_one({"_id": user_id}, {"$set": updates})

    return jsonify({"message": "Profile updated successfully"})