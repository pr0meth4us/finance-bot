from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Blueprint, jsonify, g, current_app, request
from bson import ObjectId
from pymongo import ReturnDocument
import requests
from requests.auth import HTTPBasicAuth

from app.utils.db import settings_collection, get_db
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
    # Ensure email is in the top level response so frontend auth guard sees it
    response_data['email'] = user_email

    return jsonify({
        "profile": response_data,
        "email": user_email,
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
        account_id = g.account_id
    except Exception:
        return jsonify({'error': 'Invalid session'}), 400

    data = request.json
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({'error': 'Email and password are required'}), 400

    config = current_app.config
    bifrost_url = config["BIFROST_URL"].rstrip('/')
    url = f"{bifrost_url}/internal/set-credentials"

    payload = {
        "account_id": account_id,
        "email": data['email'],
        "password": data['password'],
        "proof_token": data.get('proof_token')
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


# --- DATA PRIVACY ENDPOINTS (GDPR Compliance) ---

@users_bp.route('/data/export', methods=['POST'])
@auth_required(min_role="user")
def export_user_data():
    """
    Returns a JSON dump of all data associated with the user.
    """
    try:
        account_id = ObjectId(g.account_id)
        db = get_db()

        # 1. Profile
        profile = db.settings.find_one({"account_id": account_id}, {"_id": 0})

        # 2. Transactions
        transactions = list(db.transactions.find({"account_id": account_id}, {"_id": 0}))
        for t in transactions:
            if "timestamp" in t: t["timestamp"] = t["timestamp"].isoformat()

        # 3. Debts
        debts = list(db.debts.find({"account_id": account_id}, {"_id": 0}))
        for d in debts:
            if "created_at" in d: d["created_at"] = d["created_at"].isoformat()

        return jsonify({
            "profile": profile,
            "transactions": transactions,
            "debts": debts,
            "generated_at": datetime.now(UTC_TZ).isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Export failed: {e}")
        return jsonify({"error": "Failed to export data"}), 500


@users_bp.route('/data/delete', methods=['DELETE'])
@auth_required(min_role="user")
def delete_account():
    """
    Permanently deletes all user data and the Bifrost account.
    """
    try:
        account_id_str = g.account_id
        account_id_obj = ObjectId(account_id_str)
        db = get_db()

        # 1. Delete Local Data
        db.transactions.delete_many({"account_id": account_id_obj})
        db.debts.delete_many({"account_id": account_id_obj})
        db.reminders.delete_many({"account_id": account_id_obj})
        db.settings.delete_one({"account_id": account_id_obj})
        db.users.delete_one({"_id": account_id_obj})  # Legacy map

        # 2. Delete Identity (Bifrost)
        config = current_app.config
        bifrost_url = config["BIFROST_URL"].rstrip('/')
        url = f"{bifrost_url}/internal/users/{account_id_str}"

        auth = HTTPBasicAuth(config["BIFROST_CLIENT_ID"], config["BIFROST_CLIENT_SECRET"])
        requests.delete(url, auth=auth, timeout=5)

        return jsonify({"message": "Account permanently deleted."})

    except Exception as e:
        current_app.logger.error(f"Delete account failed: {e}")
        return jsonify({"error": "Failed to delete account"}), 500


# --- ADMIN MANAGEMENT ENDPOINTS ---

@users_bp.route('/admin/list', methods=['GET'])
@auth_required(min_role="admin")
def list_all_users():
    """
    Lists all users for admin management.
    """
    try:
        db = get_db()
        # Join settings with legacy users collection if needed, or just list settings profiles
        profiles = list(db.settings.find({}, {"account_id": 1, "name_en": 1, "name_km": 1, "created_at": 1}))

        results = []
        for p in profiles:
            p["_id"] = str(p.get("account_id"))
            del p["account_id"]
            if "created_at" in p: p["created_at"] = p["created_at"].isoformat()
            results.append(p)

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@users_bp.route('/admin/user/<target_id>', methods=['DELETE'])
@auth_required(min_role="admin")
def admin_delete_user(target_id):
    """
    Admin endpoint to delete a specific user.
    """
    try:
        oid = ObjectId(target_id)
        db = get_db()

        # 1. Delete Local
        db.transactions.delete_many({"account_id": oid})
        db.debts.delete_many({"account_id": oid})
        db.reminders.delete_many({"account_id": oid})
        db.settings.delete_one({"account_id": oid})

        # 2. Delete Identity (Bifrost)
        config = current_app.config
        bifrost_url = config["BIFROST_URL"].rstrip('/')
        url = f"{bifrost_url}/internal/users/{target_id}"
        auth = HTTPBasicAuth(config["BIFROST_CLIENT_ID"], config["BIFROST_CLIENT_SECRET"])
        requests.delete(url, auth=auth, timeout=5)

        return jsonify({"message": f"User {target_id} deleted."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500