# --- Start of file: web_service/app/auth/routes.py ---

from flask import Blueprint, request, jsonify
from datetime import datetime
from bson import ObjectId
# from app import get_db  <-- REMOVED PYMONGO
from app.utils.data_api import call_data_api  # <-- NEW IMPORT
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
    """
    Serializes user document for JSON.
    The Data API returns _id as {"$oid": "..."}
    We must convert this to just the string.
    """
    if '_id' in user and isinstance(user['_id'], dict) and '$oid' in user['_id']:
        user['_id'] = user['_id']['$oid']
    return user


@auth_bp.route('/find_or_create', methods=['POST'])
def find_or_create_user():
    """
    This is the primary authentication endpoint for the bot.
    It finds a user by their telegram_id or creates them if they don't exist.
    """
    log.info("/auth/find_or_create POST request received.")

    data = request.json
    log.info(f"Request data: {data}")
    telegram_user_id = data.get('telegram_user_id')

    if not telegram_user_id:
        log.warning("Request failed: telegram_user_id is required.")
        return jsonify({"error": "telegram_user_id is required"}), 400

    telegram_user_id = str(telegram_user_id)

    # --- REFACTOR: Use Data API to find user ---
    find_payload = {
        "collection": "users",
        "filter": {"telegram_user_id": telegram_user_id}
    }

    response_json, status_code = call_data_api("findOne", find_payload)

    if status_code != 200:
        log.error(f"Data API findOne failed with status {status_code}")
        return jsonify(response_json), status_code

    user = response_json.get("document")
    # --- END REFACTOR ---

    if not user:
        log.info(f"User {telegram_user_id} not found. Creating new user...")
        default_profile = get_default_settings_for_user(telegram_user_id)

        new_user_doc = {
            "telegram_user_id": telegram_user_id,
            "created_at": {"$date": datetime.now(UTC_TZ).isoformat().replace('+00:00', 'Z')}, # Use Data API date format
            "onboarding_complete": False,
            **default_profile
        }

        # --- REFACTOR: Use Data API to insert user ---
        insert_payload = {
            "collection": "users",
            "document": new_user_doc
        }

        insert_res, insert_status = call_data_api("insertOne", insert_payload)

        if insert_status != 201: # 201 Created
            log.error(f"Data API insertOne failed with status {insert_status}")
            return jsonify(insert_res), insert_status

        # Manually construct the user object after insert
        user = new_user_doc
        user['_id'] = insert_res.get('insertedId') # This is just the string
        # --- END REFACTOR ---

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