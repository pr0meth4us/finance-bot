from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Blueprint, jsonify, g, current_app, request
from bson import ObjectId
from pymongo import ReturnDocument
import requests
from requests.auth import HTTPBasicAuth

from app.utils.db import settings_collection
from app.utils.auth import auth_required
from app.utils.serializers import serialize_profile

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


def _get_default_settings(account_id_obj):
    """Generates the default user profile document."""
    return {
        "account_id": account_id_obj,
        "settings": {
            "language": "en",
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
        },
        "onboarding_complete": False,
        "created_at": datetime.now(UTC_TZ)
    }


@users_bp.route('/me', methods=['GET'])
@auth_required(min_role="user")
def get_my_profile():
    """
    Finds or creates the user's profile in the settings collection.
    Returns the profile document, the user's role, AND email from auth check.
    """
    try:
        account_id = ObjectId(g.account_id)
    except Exception:
        return jsonify({'error': 'Invalid account_id format'}), 400

    user_role = g.role

    # g.email is populated by our updated auth_required decorator
    user_email = getattr(g, 'email', None)

    # Atomically find or create the profile
    user_profile = settings_collection().find_one_and_update(
        {'account_id': account_id},
        {'$setOnInsert': _get_default_settings(account_id)},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )

    if not user_profile:
        current_app.logger.error(f"Failed to find or create profile for {account_id}")
        return jsonify({"error": "Failed to find or create user profile"}), 500

    # Merge the email from the Identity Provider into the response
    response_data = serialize_profile(user_profile)
    response_data['email'] = user_email

    return jsonify({
        "profile": response_data,
        "role": user_role
    }), 200


@users_bp.route('/credentials', methods=['POST'])
@auth_required(min_role="user")
def set_credentials():
    """
    Updates the email and password for the current user via Bifrost.
    Proxies the request to Bifrost's internal API.
    """
    try:
        account_id = g.account_id  # String from auth decorator
    except Exception:
        return jsonify({'error': 'Invalid session'}), 400

    data = request.json
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({'error': 'Email and password are required'}), 400

    # Server-to-Server call to Bifrost
    config = current_app.config
    bifrost_url = config["BIFROST_URL"].rstrip('/')
    url = f"{bifrost_url}/internal/set-credentials"

    payload = {
        "account_id": account_id,
        "email": data['email'],
        "password": data['password']
    }

    try:
        auth = HTTPBasicAuth(config["BIFROST_CLIENT_ID"], config["BIFROST_CLIENT_SECRET"])
        response = requests.post(url, json=payload, auth=auth, timeout=10)

        if response.status_code == 200:
            return jsonify({"message": "Credentials updated successfully"})

        # Pass through Bifrost errors (e.g., "Email already in use")
        try:
            err = response.json()
            return jsonify(err), response.status_code
        except:
            return jsonify({"error": "Failed to update credentials"}), response.status_code

    except Exception as e:
        current_app.logger.error(f"Failed to contact Bifrost: {e}")
        return jsonify({"error": "Internal service error"}), 500