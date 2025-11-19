# web_service/app/auth/routes.py

from flask import Blueprint, request, jsonify
from datetime import datetime
from bson import ObjectId
from app import get_db
from zoneinfo import ZoneInfo
import logging

log = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
UTC_TZ = ZoneInfo("UTC")

# --- COMMERCIAL CONFIGURATION ---

# 1. The "Basic" List (For Free Users)
# Minimal viable product. Good for survival, bad for lifestyle tracking.
BASIC_EXPENSE_CATEGORIES = [
    "Food", "Transport", "Bills", "Work"
]
BASIC_INCOME_CATEGORIES = [
    "Salary", "Allowance"
]

# 2. The "Full" Default List (For Premium Users, or upsell target)
# This includes "Fun" and "Growth" categories.
FULL_EXPENSE_CATEGORIES = [
    "Food", "Drink", "Transport", "Shopping", "Bills", "Utilities",
    "Entertainment", "Personal Care", "Work", "Alcohol", "For Others",
    "Health", "Investment", "Forgot", "Travel", "Education"
]
FULL_INCOME_CATEGORIES = [
    "Salary", "Bonus", "Freelance", "Commission", "Allowance", "Gift",
    "Investment", "Other"
]

def get_default_settings_for_user():
    """
    Generates the default user profile document.
    CRITICAL: New users start with BASIC categories only.
    """
    return {
        "name_en": None,
        "name_km": None,
        "role": "user",
        "subscription_status": "inactive",
        "subscription_tier": "free", # Explicitly track tier
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
            # --- FEATURE FENCING ---
            "categories": {
                "expense": BASIC_EXPENSE_CATEGORIES,
                "income": BASIC_INCOME_CATEGORIES
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
        # New user? Give them the restricted BASIC profile
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

    # Check active status (for banning/suspension logic)
    if user.get('subscription_status') == 'banned':
         return jsonify({"error": "Account suspended."}), 403

    return jsonify(serialize_user(user))