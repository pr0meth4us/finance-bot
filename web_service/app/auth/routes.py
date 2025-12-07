from flask import Blueprint, request, jsonify, g, current_app, make_response
from datetime import datetime
from bson import ObjectId
from zoneinfo import ZoneInfo
import requests
from app import get_db
from app.utils.auth import auth_required

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
    if not user:
        return None

    if '_id' in user and isinstance(user['_id'], ObjectId):
        user['_id'] = str(user['_id'])

    if 'created_at' in user and isinstance(user['created_at'], datetime):
        user['created_at'] = user['created_at'].isoformat()

    return user


# ---------------------------------------------------------------------
# BIFROST PROXY ROUTES
# ---------------------------------------------------------------------

@auth_bp.route('/request-email-otp', methods=['POST', 'OPTIONS'])
def proxy_request_otp():
    """
    Proxies the OTP request to Bifrost.
    Injects the BIFROST_CLIENT_ID so the frontend doesn't need to know it.
    """
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    bifrost_url = current_app.config['BIFROST_URL']
    client_id = current_app.config['BIFROST_CLIENT_ID']
    target_url = f"{bifrost_url}/auth/api/request-email-otp"

    # Get payload from frontend (contains email)
    payload = request.json or {}

    # INJECT CLIENT ID
    payload['client_id'] = client_id

    try:
        # Forward the modified payload to Bifrost
        resp = requests.post(target_url, json=payload, timeout=10)

        # Return Bifrost's response to the frontend
        return jsonify(resp.json()), resp.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Bifrost Proxy Error: {e}")
        return jsonify({"error": "Failed to contact Authentication Service"}), 502


@auth_bp.route('/verify-email-otp', methods=['POST', 'OPTIONS'])
def proxy_verify_otp():
    """
    Proxies the OTP verification to Bifrost.
    """
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    bifrost_url = current_app.config['BIFROST_URL']
    target_url = f"{bifrost_url}/auth/api/verify-email-otp"

    # Frontend sends verification_id and code, which is all Bifrost needs here
    try:
        resp = requests.post(target_url, json=request.json, timeout=10)
        return jsonify(resp.json()), resp.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Bifrost Proxy Error: {e}")
        return jsonify({"error": "Failed to contact Authentication Service"}), 502


# ---------------------------------------------------------------------
# USER SYNC & PROFILE ROUTES
# ---------------------------------------------------------------------

@auth_bp.route('/find_or_create', methods=['POST', 'OPTIONS'])
def find_or_create_user():
    """
    Finds a user by their telegram_id or creates them if they don't exist.
    Called by Telegram/Bifrost.
    """
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    try:
        db = get_db()
    except Exception as e:
        return jsonify({"error": "Failed to connect to database", "details": str(e)}), 500

    data = request.json or {}
    telegram_user_id = data.get('telegram_user_id')

    if not telegram_user_id:
        return jsonify({"error": "telegram_user_id is required"}), 400

    telegram_user_id = str(telegram_user_id)

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

    return jsonify(serialize_user(user)), 200


@auth_bp.route('/me', methods=['GET', 'OPTIONS'])
@auth_required(min_role="user")
def get_current_user():
    """
    Returns the profile of the currently authenticated user.
    """
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    db = get_db()
    try:
        user_id = ObjectId(g.account_id)
    except Exception:
        return jsonify({"error": "Invalid user ID from token"}), 400

    user = db.users.find_one({"_id": user_id})
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify(serialize_user(user)), 200


@auth_bp.route('/profile', methods=['PUT', 'OPTIONS'])
@auth_required(min_role="user")
def update_profile():
    """
    Updates the user's profile (currently only email).
    """
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    db = get_db()
    try:
        user_id = ObjectId(g.account_id)
    except Exception:
        return jsonify({"error": "Invalid user ID from token"}), 400

    data = request.json or {}
    updates = {}

    if 'email' in data:
        updates['email'] = data['email']

    if not updates:
        return jsonify({"error": "No fields to update"}), 400

    db.users.update_one({"_id": user_id}, {"$set": updates})
    updated = db.users.find_one({"_id": user_id})

    return jsonify({
        "message": "Profile updated successfully",
        "user": serialize_user(updated)
    }), 200