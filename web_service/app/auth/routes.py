from flask import Blueprint, request, jsonify, current_app, g
from app.models import User
from app.utils.auth import create_jwt, auth_required, decode_jwt, service_auth_required, invalidate_token_cache
from app import get_db
from app.utils.db import settings_collection
import requests
from requests.auth import HTTPBasicAuth
import os
from bson import ObjectId
import hmac
import hashlib

auth_bp = Blueprint('auth', __name__)

BIFROST_URL = os.getenv("BIFROST_URL", "http://bifrost:5000")
BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID")
BIFROST_CLIENT_SECRET = os.getenv("BIFROST_CLIENT_SECRET")


# --- HELPER: Send Telegram Notification ---
def send_telegram_alert(telegram_id, message):
    """
    Sends a message to a specific Telegram user via the Bot API.
    """
    bot_token = os.getenv("TELEGRAM_TOKEN") or current_app.config.get("TELEGRAM_TOKEN")

    if not bot_token:
        current_app.logger.error("❌ Notification Failed: TELEGRAM_TOKEN not found in environment.")
        return

    if not telegram_id:
        current_app.logger.warning("⚠️ Notification Skipped: No telegram_id provided.")
        return

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": telegram_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code != 200:
            current_app.logger.error(f"❌ Telegram API Error {resp.status_code}: {resp.text}")
        else:
            current_app.logger.info(f"✅ Notification sent to {telegram_id}")

    except Exception as e:
        current_app.logger.error(f"❌ Failed to send Telegram alert: {e}")


# --- WEB AUTHENTICATION ---

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    existing = User.find_by_email(email)
    if existing:
        return jsonify({"error": "Email already exists"}), 409

    user = User.create_from_email(email, password)
    token = create_jwt(str(user['_id']), user.get('roles', ['user']))

    return jsonify({
        "message": "Registration successful",
        "token": token,
        "user": {
            "id": str(user['_id']),
            "email": user['email'],
            "onboarding_complete": False
        }
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.find_by_email(email)
    if user and User.verify_password(user, password):
        token = create_jwt(str(user['_id']), user.get('roles', ['user']))

        # Check onboarding status
        profile = get_db().settings.find_one({"account_id": user['_id']})
        onboarding = profile.get('onboarding_complete', False) if profile else False

        return jsonify({
            "token": token,
            "user": {
                "id": str(user['_id']),
                "email": user['email'],
                "telegram_connected": bool(user.get('telegram_id')),
                "onboarding_complete": onboarding
            }
        }), 200

    return jsonify({"error": "Invalid credentials"}), 401


# --- TELEGRAM -> WEB LOGIN FLOW ---

@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp_and_login():
    """
    Receives a 6-digit code from the Frontend.
    Calls Bifrost to verify it. If valid, finds/creates the User profile via Telegram ID.
    """
    data = request.get_json()
    code = data.get('code')

    if not code:
        return jsonify({"error": "Code required"}), 400

    # 1. Verify Code with Bifrost
    try:
        res = requests.post(
            f"{BIFROST_URL}/internal/verify-otp",
            json={"code": code},
            auth=(BIFROST_CLIENT_ID, BIFROST_CLIENT_SECRET),
            timeout=5
        )
        res.raise_for_status()
        bifrost_data = res.json()

        if not bifrost_data.get('valid'):
            return jsonify({"error": "Invalid or expired code"}), 401

        telegram_id = bifrost_data.get('telegram_id')

    except Exception as e:
        current_app.logger.error(f"Bifrost OTP verify failed: {e}")
        return jsonify({"error": "Verification service unavailable"}), 503

    # 2. Find or Create User
    user = User.find_by_telegram_id(telegram_id)
    if not user:
        user = User.create_from_telegram(telegram_id, "Unknown")

    # 3. Generate Web Token
    token = create_jwt(str(user['_id']), user.get('roles', ['user']))

    profile = get_db().settings.find_one({"account_id": user['_id']})
    onboarding = profile.get('onboarding_complete', False) if profile else False

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": {
            "id": str(user['_id']),
            "telegram_id": telegram_id,
            "email_connected": bool(user.get('email')),
            "onboarding_complete": onboarding
        }
    }), 200


# --- ACCOUNT LINKING (Proxy to Bifrost) ---

@auth_bp.route('/link-account', methods=['POST'])
@auth_required(min_role="user")
def link_account():
    try:
        account_id = g.account_id
    except AttributeError:
        return jsonify({'error': 'Invalid session'}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    payload = {
        "account_id": account_id,
        **data
    }

    bifrost_url = current_app.config.get("BIFROST_URL", "").rstrip('/')
    target_url = f"{bifrost_url}/internal/link-account"
    client_id = current_app.config.get("BIFROST_CLIENT_ID")
    client_secret = current_app.config.get("BIFROST_CLIENT_SECRET")

    try:
        resp = requests.post(
            target_url,
            json=payload,
            auth=HTTPBasicAuth(client_id, client_secret),
            timeout=10
        )
        if resp.status_code == 200:
            if 'email' in data:
                try:
                    settings_collection().update_one(
                        {'account_id': ObjectId(account_id)},
                        {'$set': {'email': data['email']}}
                    )
                except Exception as e:
                    current_app.logger.warning(f"Failed to update local email cache: {e}")
            return jsonify(resp.json()), 200

        try:
            return jsonify(resp.json()), resp.status_code
        except:
            return jsonify({"error": "Upstream service error"}), resp.status_code

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Bifrost link-account failed: {e}")
        return jsonify({"error": "Link service unavailable"}), 503


@auth_bp.route('/link/initiate-telegram', methods=['POST'])
@auth_required(min_role="user")
def initiate_telegram_link():
    try:
        bifrost_url = current_app.config.get("BIFROST_URL", "").rstrip('/')
        client_id = current_app.config.get("BIFROST_CLIENT_ID")
        client_secret = current_app.config.get("BIFROST_CLIENT_SECRET")

        resp = requests.post(
            f"{bifrost_url}/internal/generate-link-token",
            json={"account_id": g.account_id},
            auth=HTTPBasicAuth(client_id, client_secret),
            timeout=5
        )
        resp.raise_for_status()
        token = resp.json().get('token')

        bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "savvify_bot")
        deep_link = f"https://t.me/{bot_username}?start=link_{token}"

        return jsonify({
            "link_url": deep_link,
            "token": token
        })
    except Exception as e:
        current_app.logger.error(f"Failed to init telegram link: {e}")
        return jsonify({"error": "Service unavailable"}), 503


@auth_bp.route('/link/complete-telegram', methods=['POST'])
def complete_telegram_link():
    data = request.get_json()
    token = data.get('token')
    telegram_id = data.get('telegram_id')

    if not token or not telegram_id:
        return jsonify({"error": "Missing token or telegram_id"}), 400

    bifrost_url = current_app.config.get("BIFROST_URL", "").rstrip('/')
    client_id = current_app.config.get("BIFROST_CLIENT_ID")
    client_secret = current_app.config.get("BIFROST_CLIENT_SECRET")

    try:
        resp = requests.post(
            f"{bifrost_url}/internal/link-account",
            json={"link_token": token, "telegram_id": telegram_id},
            auth=HTTPBasicAuth(client_id, client_secret),
            timeout=5
        )

        if resp.status_code == 200:
            return jsonify({"success": True}), 200
        else:
            return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- CACHE INVALIDATION & NOTIFICATION WEBHOOK ---

@auth_bp.route('/internal/webhook/auth-event', methods=['POST'])
def auth_event_webhook():
    """
    Receives and processes Auth Events from Bifrost (IdP).
    Handles Security (Logout), Role Updates, and Notifications.
    """
    # 1. Verify HMAC Signature
    signature = request.headers.get('X-Bifrost-Signature')
    if not signature:
        return jsonify({"error": "Missing signature"}), 401

    webhook_secret = current_app.config.get("BIFROST_WEBHOOK_SECRET")
    if not webhook_secret:
        current_app.logger.critical("❌ Configuration Error: Missing BIFROST_WEBHOOK_SECRET")
        return jsonify({"error": "Server configuration error"}), 500

    payload_bytes = request.get_data()
    try:
        expected_signature = hmac.new(
            key=webhook_secret.encode('utf-8'),
            msg=payload_bytes,
            digestmod=hashlib.sha256
        ).hexdigest()
    except Exception as e:
        return jsonify({"error": "Internal verification error"}), 500

    if not hmac.compare_digest(expected_signature, signature):
        return jsonify({"error": "Invalid signature"}), 403

    # 2. Process Event
    try:
        data = request.get_json()
        event_type = data.get('event')
        account_id = data.get('account_id')
        token = data.get('token')

        tx_id = data.get('transaction_id')
        ref_id = data.get('client_ref_id')

        current_app.logger.info(f"🔔 Webhook: [{event_type}] Acc: {account_id} | Tx: {tx_id} | Ref: {ref_id}")

        # --- Fetch User for Notifications (Robust Lookup) ---
        telegram_id = None
        try:
            # Try finding via User Auth ID
            user_auth = get_db().users.find_one({"_id": ObjectId(account_id)})
            if user_auth and user_auth.get('telegram_id'):
                telegram_id = user_auth.get('telegram_id')
            else:
                # Fallback: Check Settings (legacy or linked data)
                user_settings = get_db().settings.find_one({"account_id": ObjectId(account_id)})
                if user_settings:
                    # Sometimes stored in settings during migration
                    telegram_id = user_settings.get('telegram_id')

            if not telegram_id:
                current_app.logger.warning(f"⚠️ User {account_id} found, but no Telegram ID linked. Cannot notify.")
        except Exception as e:
            current_app.logger.warning(f"⚠️ Could not resolve user {account_id} for notification: {e}")

        # --- A. Subscription Events ---
        if event_type == 'subscription_success':
            # 1. Update DB Role
            get_db().settings.update_one(
                {"account_id": ObjectId(account_id)},
                {"$set": {"role": "premium_user"}}
            )
            current_app.logger.info(f" 🎉 Premium Activated for {account_id}")

            # 2. Notify User
            if telegram_id:
                send_telegram_alert(
                    telegram_id,
                    "🌟 **Premium Activated!**\n\nThank you for supporting Savvify. Your Premium features are now active!"
                )

            if token: invalidate_token_cache(token)
        elif event_type == 'account_update':
            # NEW: Sync updated fields directly from payload
            updates = {}
            if data.get('telegram_id'): updates['telegram_id'] = data.get('telegram_id')
            if data.get('email'): updates['email'] = data.get('email')
            if data.get('username'): updates['username'] = data.get('username')

            if updates:
                get_db().settings.update_one(
                    {"account_id": ObjectId(account_id)},
                    {"$set": updates}
                )
                current_app.logger.info(f" 📝 Profile synced via Webhook: {updates.keys()}")

            if token: invalidate_token_cache(token)

        elif event_type == 'subscription_expired':
            # 1. Downgrade DB Role
            get_db().settings.update_one(
                {"account_id": ObjectId(account_id)},
                {"$set": {"role": "user"}}
            )
            current_app.logger.info(f" 📉 Premium Expired for {account_id}")

            # 2. Notify User
            if telegram_id:
                send_telegram_alert(
                    telegram_id,
                    "⚠️ **Premium Expired**\n\nYour subscription has ended. You have been downgraded to the Free tier."
                )

            if token: invalidate_token_cache(token)

        # --- Other Events (Security/Profile) ---
        elif event_type in ['invalidation', 'security_password_change', 'account_role_change', 'account_update']:
            if token: invalidate_token_cache(token)
            if event_type == 'security_password_change' and telegram_id:
                send_telegram_alert(telegram_id, "🔐 **Security Alert**: Your password was just changed.")
            current_app.logger.info(f" ℹ️ Processed {event_type}")

        else:
            current_app.logger.warning(f" ❓ Unknown event type: {event_type}")

        return jsonify({"status": "processed", "event": event_type}), 200

    except Exception as e:
        current_app.logger.error(f"❌ Webhook Processing Error: {e}")
        return jsonify({"error": "Processing failed"}), 400