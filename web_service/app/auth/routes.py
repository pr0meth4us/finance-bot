from flask import Blueprint, request, jsonify, current_app, g
from app.models import User
from app.utils.auth import auth_required, service_auth_required, invalidate_token_cache, login_required
from app import get_db
from app.utils.db import settings_collection
import requests
from requests.auth import HTTPBasicAuth
import os
from bson import ObjectId
import hmac
import hashlib
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

BIFROST_URL = os.getenv("BIFROST_URL", "http://bifrost:5000")
BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID")
BIFROST_CLIENT_SECRET = os.getenv("BIFROST_CLIENT_SECRET")
BIFROST_TIMEOUT = 60


# --- HELPER: Send Telegram Notification ---
def send_telegram_alert(telegram_id, message):
    """Sends a security alert to the user's Telegram."""
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

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Proxies login credentials to Bifrost and returns the Bifrost JWT.
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    try:
        # Call Bifrost API
        response = requests.post(
            f"{BIFROST_URL}/auth/api/login",
            json={
                "client_id": BIFROST_CLIENT_ID,
                "email": email,
                "password": password
            },
            timeout=BIFROST_TIMEOUT
        )

        if response.status_code == 200:
            # Success! Return the Bifrost JWT to the frontend
            return jsonify(response.json()), 200
        else:
            # Pass through the error from Bifrost
            return jsonify(response.json()), response.status_code

    except Exception as e:
        current_app.logger.error(f"Bifrost Login Proxy Error: {e}")
        return jsonify({"error": "Authentication service unavailable"}), 503


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Bifrost does not allow open registration via API (requires OTP).
    We direct the user to the OTP flow.
    """
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email required"}), 400

    # Trigger Bifrost OTP Flow
    try:
        response = requests.post(
            f"{BIFROST_URL}/auth/api/request-email-otp",
            json={
                "client_id": BIFROST_CLIENT_ID,
                "email": email
            },
            timeout=BIFROST_TIMEOUT
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": "Registration service unavailable"}), 503


@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp_and_login():
    """
    Proxies OTP verification to Bifrost (for Telegram/Email login codes).
    """
    data = request.get_json()
    code = data.get('code')

    if not code:
        return jsonify({"error": "Code required"}), 400

    try:
        # Call Bifrost API
        response = requests.post(
            f"{BIFROST_URL}/auth/api/verify-otp-login",
            json={
                "client_id": BIFROST_CLIENT_ID,
                "code": code
            },
            timeout=BIFROST_TIMEOUT
        )
        return jsonify(response.json()), response.status_code

    except Exception as e:
        current_app.logger.error(f"Bifrost OTP Proxy Error: {e}")
        return jsonify({"error": "Verification service unavailable"}), 503


@auth_bp.route('/telegram-login', methods=['POST'])
def telegram_login():
    """
    Proxies login via Telegram Widget to Bifrost.
    """
    data = request.get_json()
    telegram_data = data.get('telegram_data')

    if not telegram_data:
        return jsonify({"error": "telegram_data object required"}), 400

    payload = {
        "client_id": BIFROST_CLIENT_ID,
        "telegram_data": telegram_data
    }

    try:
        # Call Bifrost
        # FIX: Increased timeout from 10s to BIFROST_TIMEOUT (60s) to handle cold starts
        response = requests.post(
            f"{BIFROST_URL}/auth/api/telegram-login",
            json=payload,
            timeout=BIFROST_TIMEOUT
        )
        return jsonify(response.json()), response.status_code

    except Exception as e:
        current_app.logger.error(f"Bifrost Telegram Login Error: {e}")
        return jsonify({"error": "Authentication service unavailable"}), 503


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    """
    Returns the current user profile (synced from Bifrost).
    """
    user = g.user
    return jsonify({
        "id": str(user['_id']),
        "email": user.get('email'),
        "role": user.get('role', 'user'),
        "telegram_id": user.get('telegram_id'),
        "display_name": user.get('display_name')
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
            timeout=BIFROST_TIMEOUT
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
            timeout=BIFROST_TIMEOUT
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


@auth_bp.route('/link-command', methods=['POST'])
@auth_required(min_role="user")
def generate_link_command():
    """
    Generates a secure '/link <token>' command string for manual entry in Telegram.
    Reuses Bifrost's link-token generation logic.
    """
    try:
        bifrost_url = current_app.config.get("BIFROST_URL", "").rstrip('/')
        client_id = current_app.config.get("BIFROST_CLIENT_ID")
        client_secret = current_app.config.get("BIFROST_CLIENT_SECRET")

        # Reuse the generate-link-token endpoint from Bifrost
        resp = requests.post(
            f"{bifrost_url}/internal/generate-link-token",
            json={"account_id": g.account_id},
            auth=HTTPBasicAuth(client_id, client_secret),
            timeout=BIFROST_TIMEOUT
        )
        resp.raise_for_status()
        token = resp.json().get('token')

        if not token:
            return jsonify({"error": "Failed to generate token"}), 500

        # Return the manual command string
        return jsonify({
            "command": f"/link {token}",
            "token": token,
            "expires_in": "10 minutes"
        })

    except Exception as e:
        current_app.logger.error(f"Failed to generate link command: {e}")
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
            timeout=BIFROST_TIMEOUT
        )

        if resp.status_code == 200:
            return jsonify({"success": True}), 200
        else:
            return jsonify(resp.json()), resp.status_code

    except Exception as e:
        current_app.logger.error(f"Telegram link completion failed: {e}")
        return jsonify({"error": "Internal Error"}), 500


# --- INTERNAL WEBHOOKS ---

@auth_bp.route('/internal/webhook/auth-event', methods=['POST'])
def auth_event_webhook():
    signature = request.headers.get('X-Bifrost-Signature')
    webhook_secret = current_app.config.get("BIFROST_WEBHOOK_SECRET")

    if not signature or not webhook_secret:
        return jsonify({"error": "Config error"}), 400

    payload_bytes = request.get_data()
    expected = hmac.new(webhook_secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
        return jsonify({"error": "Invalid signature"}), 403

    try:
        data = request.get_json()
        event_type = data.get('event')
        account_id = data.get('account_id')
        token = data.get('token')

        current_app.logger.info(f"🔔 Webhook: [{event_type}] Acc: {account_id}")

        # --- Fetch User for Notifications ---
        user = User.get_by_account_id(account_id)
        telegram_id = user.telegram_id if user else None

        # --- A. Subscription Events ---
        if event_type == 'subscription_success':
            # Extract Bifrost 2.3.3 Data
            extra = data.get('extra_data', {})
            expires_at = extra.get('expires_at')
            duration = extra.get('duration')

            # 1. Update DB
            update_data = {"role": "premium_user"}
            if expires_at:
                update_data["expires_at"] = expires_at

            get_db().settings.update_one(
                {"account_id": ObjectId(account_id)},
                {"$set": update_data}
            )
            current_app.logger.info(f"   🎉 Premium Activated for {account_id}")

            # 2. Notify User with details
            if telegram_id:
                msg = "🌟 **Premium Activated!**\n\nThank you for supporting Savvify."

                # Format Duration
                if duration:
                    d_map = {"1m": "1 Month", "1y": "1 Year"}
                    readable_duration = d_map.get(duration, duration)
                    msg += f"\n\n**Plan:** {readable_duration}"

                # Format Expiry
                if expires_at:
                    try:
                        # Assuming ISO format (e.g. 2026-02-23T10:00:00Z)
                        dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        date_str = dt.strftime('%Y-%m-%d')
                        msg += f"\n**Valid until:** {date_str}"
                    except Exception:
                        pass  # Fallback if format differs

                msg += "\n\nYour Premium features are now active!"

                send_telegram_alert(telegram_id, msg)
            else:
                current_app.logger.warning(f"⚠️ Could not notify user {account_id}: No Telegram ID found.")

            # 3. Invalidate Cache
            if token:
                invalidate_token_cache(token)

        elif event_type == 'subscription_expired':
            # 1. Downgrade DB Role
            get_db().settings.update_one(
                {"account_id": ObjectId(account_id)},
                {"$set": {"role": "user"}}
            )
            current_app.logger.info(f"   📉 Premium Expired for {account_id}")

            # 2. Notify User
            if telegram_id:
                send_telegram_alert(
                    telegram_id,
                    "⚠️ **Premium Expired**\n\nYour subscription has ended. You have been downgraded to the Free tier."
                )

            # 3. Invalidate Cache
            if token:
                invalidate_token_cache(token)

        # --- B. Profile Update Sync ---
        elif event_type == 'account_update':
            # NEW: Sync updated fields directly from payload
            updates = {}
            if data.get('telegram_id'):
                updates['telegram_id'] = data.get('telegram_id')
            if data.get('email'):
                updates['email'] = data.get('email')
            if data.get('username'):
                updates['username'] = data.get('username')

            if updates:
                get_db().settings.update_one(
                    {"account_id": ObjectId(account_id)},
                    {"$set": updates}
                )
                current_app.logger.info(f"   📝 Profile synced via Webhook: {list(updates.keys())}")

            if token:
                invalidate_token_cache(token)

        # --- C. Security Events ---
        elif event_type in ['invalidation', 'security_password_change']:
            if token:
                invalidate_token_cache(token)

            if event_type == 'security_password_change' and telegram_id:
                send_telegram_alert(telegram_id, "🔐 **Security Alert**: Your password was just changed.")

        return jsonify({"status": "processed", "event": event_type}), 200

    except Exception as e:
        current_app.logger.error(f"Webhook error: {e}")
        return jsonify({"error": "Failed"}), 500