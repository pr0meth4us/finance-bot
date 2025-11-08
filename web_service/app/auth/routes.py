# --- Start of new file: web_service/app/auth/routes.py ---

from flask import Blueprint, request, jsonify
from datetime import datetime
from bson import ObjectId
from app import get_db
from zoneinfo import ZoneInfo

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
UTC_TZ = ZoneInfo("UTC")

# --- Your hardcoded Admin configuration ---
ADMIN_TELEGRAM_ID = "1836585300"
ADMIN_REMINDER_CHAT_ID = "-1003192465072"
ADMIN_REPORT_CHAT_ID = "-4876783109"

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
            "subscription_status": "active", # Admins are always active
            "settings": {
                "language": "en",
                "rate_preference": "live", # 'live' or 'fixed'
                "fixed_rate": 4100,
                "reminder_chat_id": ADMIN_REMINDER_CHAT_ID,
                "report_chat_id": ADMIN_REPORT_CHAT_ID
            }
        }
    else:
        # Default for a new, non-admin user
        return {
            "name": "New User",
            "role": "user",
            "subscription_status": "inactive", # Default to inactive until they subscribe
            "settings": {
                "language": "en",
                "rate_preference": "live",
                "fixed_rate": 4100,
                "reminder_chat_id": None, # Must be set by an admin
                "report_chat_id": None   # Must be set by an admin
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

    # Ensure telegram_user_id is a string for consistent lookups
    telegram_user_id = str(telegram_user_id)

    user = db.users.find_one({"telegram_user_id": telegram_user_id})

    if not user:
        # User doesn't exist, create them
        default_profile = get_default_settings_for_user(telegram_user_id)

        new_user_doc = {
            "telegram_user_id": telegram_user_id,
            "created_at": datetime.now(UTC_TZ),
            **default_profile
        }

        result = db.users.insert_one(new_user_doc)
        user = db.users.find_one({"_id": result.inserted_id})

        # This is their first time, flag for onboarding
        user['is_new_user'] = True

    if not user:
        return jsonify({"error": "Failed to find or create user"}), 500

    # Check subscription status (admins are always active)
    if user['role'] != 'admin' and user['subscription_status'] != 'active':
        return jsonify({
            "error": "Subscription not active. Please subscribe to use this bot."
        }), 403 # Forbidden

    return jsonify(serialize_user(user))
# --- End of new file ---