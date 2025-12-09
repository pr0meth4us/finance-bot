from flask import Blueprint, request, jsonify, g, current_app
from datetime import datetime
from bson import ObjectId
from zoneinfo import ZoneInfo
import requests
from app import get_db
# Import validation logic
from app.utils.auth import auth_required, _validate_token_with_bifrost, service_auth_required
from app.utils.serializers import serialize_profile

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
    if not user:
        return None
    if '_id' in user and isinstance(user['_id'], ObjectId):
        user['_id'] = str(user['_id'])
    if 'created_at' in user and isinstance(user['created_at'], datetime):
        user['created_at'] = user['created_at'].isoformat()
    return user


def _try_get_account_id_from_header():
    """Helper to extract account_id from the Authorization header if present."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    try:
        scheme, token = auth_header.split(maxsplit=1)
        if scheme.lower() != 'bearer':
            return None

        config = current_app.config
        success, data, _ = _validate_token_with_bifrost(
            token,
            config["BIFROST_URL"],
            config["BIFROST_CLIENT_ID"],
            config["BIFROST_CLIENT_SECRET"]
        )

        if success and data.get("is_valid"):
            return data.get("account_id")

    except Exception as e:
        current_app.logger.warning(f"Optional auth check failed in proxy: {e}")

    return None


# ---------------------------------------------------------------------
# BIFROST PROXY ROUTES
# ---------------------------------------------------------------------

@auth_bp.route('/request-email-otp', methods=['POST', 'OPTIONS'])
def proxy_request_otp():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    bifrost_url = current_app.config['BIFROST_URL']
    client_id = current_app.config['BIFROST_CLIENT_ID']
    target_url = f"{bifrost_url}/auth/api/request-email-otp"

    payload = request.json or {}
    payload['client_id'] = client_id

    # INJECT ACCOUNT ID (This prevents creating a new duplicate account)
    account_id = _try_get_account_id_from_header()
    if account_id:
        payload['account_id'] = account_id
        current_app.logger.info(f"Linking OTP request to existing account: {account_id}")
    else:
        current_app.logger.info("OTP request is anonymous (New Account Flow)")

    try:
        resp = requests.post(target_url, json=payload, timeout=10)
        # Forward Bifrost status code and JSON directly
        return jsonify(resp.json()), resp.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Bifrost Proxy Error: {e}")
        return jsonify({"error": "Failed to contact Authentication Service"}), 502


@auth_bp.route('/verify-email-otp', methods=['POST', 'OPTIONS'])
def proxy_verify_otp():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    bifrost_url = current_app.config['BIFROST_URL']
    target_url = f"{bifrost_url}/auth/api/verify-email-otp"

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
@service_auth_required
def find_or_create_user():
    """
    Called by Bot (via Bifrost potentially) to map Telegram ID to Account.
    """
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    db = get_db()
    data = request.json or {}
    telegram_user_id = data.get('telegram_user_id')

    if not telegram_user_id:
        return jsonify({"error": "telegram_user_id is required"}), 400

    telegram_user_id = str(telegram_user_id)

    # Check 'users' collection (The Telegram Map)
    user = db.users.find_one({"telegram_user_id": telegram_user_id})

    if not user:
        default_profile = get_default_settings_for_user()
        new_user_doc = {
            "telegram_user_id": telegram_user_id,
            "created_at": datetime.now(UTC_TZ),
            "onboarding_complete": False,
            **default_profile
        }
        result = db.users.insert_one(new_user_doc)
        user = db.users.find_one({"_id": result.inserted_id})

    return jsonify(serialize_user(user)), 200


@auth_bp.route('/me', methods=['GET', 'OPTIONS'])
@auth_required(min_role="user")
def get_current_user():
    """
    Legacy endpoint. Tries to find user in 'users' collection (Telegram map).
    If not found (Web user), falls back to 'settings' collection.
    """
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    db = get_db()
    try:
        user_id = ObjectId(g.account_id)
    except Exception:
        return jsonify({"error": "Invalid user ID from token"}), 400

    # 1. Try Users Collection (Legacy / Telegram)
    user = db.users.find_one({"_id": user_id})
    if user:
        return jsonify(serialize_user(user)), 200

    # 2. Fallback to Settings Collection (Web-only users)
    settings = db.settings.find_one({"account_id": user_id})
    if settings:
        # Construct a minimal user object
        user_obj = {
            "_id": str(user_id),
            "email": g.email,
            "name_en": settings.get("name_en"),
            "settings": settings.get("settings")
        }
        return jsonify(user_obj), 200

    return jsonify({"error": "User not found"}), 404


@auth_bp.route('/profile', methods=['PUT', 'OPTIONS'])
@auth_required(min_role="user")
def update_profile():
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

    # Update both collections to be safe
    db.users.update_one({"_id": user_id}, {"$set": updates})
    db.settings.update_one({"account_id": user_id}, {"$set": updates})

    return jsonify({"message": "Profile updated successfully"}), 200