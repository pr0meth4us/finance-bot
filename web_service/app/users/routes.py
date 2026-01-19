from flask import Blueprint, jsonify, g, current_app, request
from bson import ObjectId
from requests.auth import HTTPBasicAuth
import requests
import jwt
from datetime import datetime
from zoneinfo import ZoneInfo

from app.utils.db import settings_collection, get_db
from app.utils.auth import auth_required
from app.utils.serializers import serialize_profile
from app.models import User

users_bp = Blueprint('users', __name__, url_prefix='/users')
UTC_TZ = ZoneInfo("UTC")


@users_bp.route('/me', methods=['GET'])
@auth_required(min_role="user")
def get_my_profile():
    """
    Finds or creates the user's profile in the settings collection.
    Returns the profile document, the user's role, username, and email.
    """
    try:
        account_id = ObjectId(g.account_id)
    except Exception:
        return jsonify({'error': 'Invalid account_id format'}), 400

    user_role = g.role
    # g.email might be populated by auth check, but we prefer the DB record if fresh
    token_email = getattr(g, 'email', None)

    # Use the Model to find or create
    user = User.get_by_account_id(account_id)
    if not user:
        user = User.create(account_id, role=user_role, email=token_email)

    if not user:
        current_app.logger.error(f"Failed to find or create profile for {account_id}")
        return jsonify({"error": "Failed to find or create user profile"}), 500

    # Serialize the settings/profile doc
    response_profile = serialize_profile(user.doc)

    # Determine authoritative email (DB > Token)
    final_email = user.email or token_email

    # Ensure critical identity fields are in the response
    return jsonify({
        "profile": response_profile,
        "username": user.username,
        "display_name": user.display_name,
        "email": final_email,
        "role": user_role
    }), 200


@users_bp.route('/me', methods=['PUT'])
@auth_required(min_role="user")
def update_me():
    """
    Updates the user profile (Display Name, Email, Username).
    - Display Name: Directly updated.
    - Username: Directly updated (checked for uniqueness by Bifrost).
    - Email: Requires a valid 'proof_token' from the OTP flow.
    """
    try:
        account_id = ObjectId(g.account_id)
        account_id_str = str(account_id)
    except Exception:
        return jsonify({'error': 'Invalid session'}), 400

    data = request.json or {}
    updates = {}
    bifrost_updates = {}

    # 1. Handle Display Name
    # Support both new 'display_name' and legacy 'name_en'
    if 'display_name' in data or 'name_en' in data:
        # Get the first non-None value, avoiding the "empty string is falsy" trap
        raw_val = data.get('display_name')
        if raw_val is None:
            raw_val = data.get('name_en')

        if isinstance(raw_val, str):
            clean_name = raw_val.strip()
            if clean_name:
                updates['display_name'] = clean_name
                updates['name_en'] = clean_name  # Keep legacy field in sync
                bifrost_updates['display_name'] = clean_name

    # 2. Handle Username
    if 'username' in data:
        raw_username = data.get('username')
        if isinstance(raw_username, str):
            clean_username = raw_username.strip().lower()
            if clean_username:
                updates['username'] = clean_username
                bifrost_updates['username'] = clean_username

    # 3. Handle Email (Secure Flow)
    if 'email' in data:
        raw_email = data.get('email')
        if isinstance(raw_email, str):
            new_email = raw_email.strip().lower()

            if new_email:
                proof_token = data.get('proof_token')

                if not proof_token:
                    return jsonify({"error": "Changing email requires verification. Please verify the new email first."}), 400

                try:
                    # Verify proof token matches the request
                    payload = jwt.decode(
                        proof_token,
                        current_app.config.get('JWT_SECRET_KEY', 'dev_secret'),
                        options={"verify_signature": False}, # Signature verified by Bifrost usually
                        algorithms=["HS256"]
                    )

                    if payload.get('email') != new_email:
                        return jsonify({"error": "Proof token does not match the requested email."}), 400

                    if payload.get('scope') != 'credential_reset':
                        return jsonify({"error": "Invalid token scope."}), 400

                    bifrost_updates['email'] = new_email
                    updates['email'] = new_email

                except Exception as e:
                    current_app.logger.error(f"Proof token check failed: {e}")
                    return jsonify({"error": "Invalid proof token"}), 400

    if not updates and not bifrost_updates:
        # This handles the case where fields were sent but empty/invalid,
        # avoiding a crash and just doing nothing.
        return jsonify({"message": "No valid changes detected"}), 200

    # 4. Sync to Bifrost (If identity fields changed)
    if bifrost_updates:
        config = current_app.config
        bifrost_url = config.get("BIFROST_URL", "").rstrip('/')
        if not bifrost_url:
            return jsonify({"error": "Bifrost URL not configured"}), 500

        url = f"{bifrost_url}/internal/users/{account_id_str}/update"

        try:
            auth = HTTPBasicAuth(config["BIFROST_CLIENT_ID"], config["BIFROST_CLIENT_SECRET"])
            resp = requests.post(url, json=bifrost_updates, auth=auth, timeout=10)

            if resp.status_code != 200:
                # Bifrost rejected the update (e.g., username taken)
                try:
                    err_msg = resp.json().get('error', 'Failed to update identity')
                except:
                    err_msg = 'Failed to update identity'
                return jsonify({"error": err_msg}), resp.status_code

        except Exception as e:
            current_app.logger.error(f"Bifrost sync failed: {e}")
            return jsonify({"error": "Failed to sync profile changes"}), 502

    # 5. Update Local DB
    if updates:
        settings_collection().update_one(
            {'account_id': account_id},
            {'$set': updates}
        )

    return jsonify({
        "message": "Profile updated successfully",
        "updates": list(updates.keys())
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
    bifrost_url = config.get("BIFROST_URL", "").rstrip('/')
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

        # Legacy cleanup if exists
        if "users" in db.list_collection_names():
            db.users.delete_one({"_id": account_id_obj})

        # 2. Delete Identity (Bifrost)
        config = current_app.config
        bifrost_url = config.get("BIFROST_URL", "").rstrip('/')
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
        # List settings profiles, now including username and display_name
        profiles = list(db.settings.find({}, {
            "account_id": 1,
            "username": 1,
            "display_name": 1,
            "name_en": 1,
            "email": 1,
            "created_at": 1
        }))

        results = []
        for p in profiles:
            p["_id"] = str(p.get("account_id"))
            del p["account_id"]
            if "created_at" in p: p["created_at"] = p["created_at"].isoformat()
            # Normalize display name for admin view
            if not p.get("display_name") and p.get("name_en"):
                p["display_name"] = p["name_en"]
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
        bifrost_url = config.get("BIFROST_URL", "").rstrip('/')
        url = f"{bifrost_url}/internal/users/{target_id}"
        auth = HTTPBasicAuth(config["BIFROST_CLIENT_ID"], config["BIFROST_CLIENT_SECRET"])
        requests.delete(url, auth=auth, timeout=5)

        return jsonify({"message": f"User {target_id} deleted."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500