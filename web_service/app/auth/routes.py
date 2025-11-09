# --- Start of file: web_service/app/auth/routes.py ---

from flask import Blueprint, request, jsonify
from datetime import datetime
from bson import ObjectId
from app import get_db
from zoneinfo import ZoneInfo
import logging

# --- DEBUG TRACING ---
log = logging.getLogger(__name__)
# --- END DEBUG TRACING ---

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
        log.info(f"User {telegram_id} is Admin. Assigning admin defaults.")
        return {
            "name": "Admin",
            "role": "admin",
            "subscription_status": "active",
            "settings": {
                "language": "en",
                "currency_mode": "dual",  # Admin defaults to dual
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
    log.info(f"User {telegram_id} is a standard user. Assigning defaults.")
    return {
        "name": "New User",
        "role": "user",
        "subscription_status": "inactive",
        "settings": {
            "language": "en",
            "currency_mode": None,  # <-- NEW: Will be set during onboarding
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
    log.info("/auth/find_or_create POST request received.")

    try:
        db = get_db()
        log.info("Database connection retrieved.")
    except Exception as e:
        log.error(f"CRITICAL: Failed to get DB connection in /auth: {e}", exc_info=True)
        return jsonify({"error": "Failed to connect to database", "details": str(e)}), 500

    data = request.json
    log.info(f"Request data: {data}")
    telegram_user_id = data.get('telegram_user_id')

    if not telegram_user_id:
        log.warning("Request failed: telegram_user_id is required.")
        return jsonify({"error": "telegram_user_id is required"}), 400

    telegram_user_id = str(telegram_user_id)
    user = None

    # --- THIS IS THE CRITICAL STEP ---
    try:
        log.info(f"Attempting to find user: {telegram_user_id}")
        log.info("Executing: db.users.find_one(...)")
        user = db.users.find_one({"telegram_user_id": telegram_user_id})
        log.info(f"db.users.find_one() result: {'User found' if user else 'User not found'}")
    except Exception as e:
        # This will catch the ServerSelectionTimeoutError
        log.error(f"CRITICAL: db.users.find_one() FAILED: {e}", exc_info=True)
        return jsonify({"error": "Database query failed", "details": str(e)}), 500
    # --- END CRITICAL STEP ---

    if not user:
        log.info(f"User {telegram_user_id} not found. Creating new user...")
        default_profile = get_default_settings_for_user(telegram_user_id)

        new_user_doc = {
            "telegram_user_id": telegram_user_id,
            "created_at": datetime.now(UTC_TZ),
            "onboarding_complete": False,
            **default_profile
        }

        try:
            log.info("Executing: db.users.insert_one(...)")
            result = db.users.insert_one(new_user_doc)
            log.info("Executing: db.users.find_one(inserted_id)")
            user = db.users.find_one({"_id": result.inserted_id})
            log.info("New user created and fetched successfully.")
        except Exception as e:
            log.error(f"CRITICAL: db.users.insert_one() FAILED: {e}", exc_info=True)
            return jsonify({"error": "Database insert failed", "details": str(e)}), 500

    if not user:
        log.error("CRITICAL: User is still None after insert logic.")
        return jsonify({"error": "Failed to find or create user"}), 500

    if user['role'] != 'admin' and user['subscription_status'] != 'active':
        log.warning(f"User {telegram_user_id} denied: Subscription not active.")
        return jsonify({
            "error": "Subscription not active. Please subscribe to use this bot."
        }), 403

    log.info(f"Auth successful for user {telegram_user_id}.")
    return jsonify(serialize_user(user))

# --- End of file ---