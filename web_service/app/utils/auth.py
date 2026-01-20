import requests
import logging
import hashlib
import hmac
import time
from functools import wraps
from flask import request, jsonify, g, current_app
from requests.auth import HTTPBasicAuth
from cachetools import TTLCache
import jwt
from datetime import datetime, timedelta
# Cache validation results for 5 minutes (300 seconds)
_token_cache = TTLCache(maxsize=1024, ttl=300)

ROLE_HIERARCHY = {
    "user": 1,
    "premium_user": 2,
    "admin": 99
}


def _get_role_level(role_name):
    """Returns the numerical level for a given role name."""
    return ROLE_HIERARCHY.get(role_name, 0)


def _validate_token_with_bifrost(token, bifrost_url, client_id, client_secret):
    """
    Validates token against Bifrost.
    """
    if token in _token_cache:
        return _token_cache[token]

    validate_url = f"{bifrost_url}/internal/validate-token"
    payload = {"jwt": token}

    try:
        # Identify ourselves to Bifrost
        auth = HTTPBasicAuth(client_id, client_secret)
        # FIX: Increased timeout to 20s to handle Bifrost cold starts
        response = requests.post(validate_url, auth=auth, json=payload, timeout=20)

        if response.status_code == 200:
            result = (True, response.json(), 200)
            _token_cache[token] = result
            return result

        elif response.status_code == 401:
            try:
                err_resp = response.json()
            except ValueError:
                err_resp = {"error": response.text}

            current_app.logger.warning(f"Bifrost Validation Failed (401): {err_resp}")

            if "is_valid" in err_resp:
                return (True, err_resp, 200)
            else:
                return (False, {"error": "Service Authentication Failed"}, 500)

        elif response.status_code == 403:
            return (False, response.json(), 403)

        else:
            current_app.logger.error(f"Bifrost unexpected status {response.status_code}: {response.text}")
            return (False, {"error": "Authentication service unavailable"}, 503)

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Bifrost Connection Error: {e}")
        return (False, {"error": "Authentication service connection error"}, 503)


def verify_telegram_login(data, bot_token):
    """
    Verifies the hash received from the Telegram Login Widget.
    Algorithm:
    1. Create a data-check-string by combining all received fields
       (except hash) sorted alphabetically in key=value format.
    2. Compute SHA256 of the bot token to get the secret key.
    3. Compute HMAC-SHA256 of the data-check-string using the secret key.
    4. Compare the result with the received hash.
    """
    if not bot_token:
        return False

    received_hash = data.get('hash')
    if not received_hash:
        return False

    # 1. Prepare Data Check String
    data_check_arr = []
    for key, value in sorted(data.items()):
        if key == 'hash':
            continue
        data_check_arr.append(f"{key}={value}")

    data_check_string = '\n'.join(data_check_arr)

    # 2. Secret Key
    secret_key = hashlib.sha256(bot_token.encode('utf-8')).digest()

    # 3. HMAC-SHA256
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # 4. Compare
    if calculated_hash != received_hash:
        return False

    # Optional: Check auth_date for freshness (e.g., within 24 hours)
    auth_date = int(data.get('auth_date', 0))
    if time.time() - auth_date > 86400:
        current_app.logger.warning("Telegram login data is stale (>24h).")
        return False

    return True


def auth_required(min_role="user"):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method == 'OPTIONS':
                return f(*args, **kwargs)

            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return jsonify({"error": "Authorization header is missing"}), 401

            try:
                scheme, token = auth_header.split(maxsplit=1)
                if scheme.lower() != 'bearer':
                    raise ValueError("Invalid scheme")
            except ValueError:
                return jsonify({"error": "Invalid Authorization header format"}), 401

            config = current_app.config

            success, data, status_code = _validate_token_with_bifrost(
                token,
                config["BIFROST_URL"],
                config["BIFROST_CLIENT_ID"],
                config["BIFROST_CLIENT_SECRET"]
            )

            if not success:
                return jsonify(data), status_code

            # Check Validity
            if not data.get("is_valid"):
                current_app.logger.warning(f"Token rejected: {data.get('error')}")
                return jsonify({"error": "Invalid or expired token"}), 401

            # Check Role
            user_role = data.get("app_specific_role", "user")
            if _get_role_level(user_role) < _get_role_level(min_role):
                return jsonify({"error": "Forbidden: Insufficient role"}), 403

            g.account_id = data.get("account_id")
            g.role = user_role
            g.email = data.get("email") # Capture email from Bifrost response

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def service_auth_required(f):
    """
    SECURITY LOCK: Ensures the request comes from a trusted service (Bifrost)
    by verifying Basic Auth credentials against our own ENV variables.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)

        auth = request.authorization
        if not auth or not auth.username or not auth.password:
            return jsonify({"error": "Service authentication required"}), 401

        # Check if the incoming credentials match our expected BIFROST_CLIENT_ID/SECRET
        # This proves the caller knows our secrets.
        expected_client_id = current_app.config["BIFROST_CLIENT_ID"]
        expected_client_secret = current_app.config["BIFROST_CLIENT_SECRET"]

        if auth.username != expected_client_id or auth.password != expected_client_secret:
            current_app.logger.warning(f"Failed service auth attempt. Claimed ID: {auth.username}")
            return jsonify({"error": "Invalid service credentials"}), 403

        return f(*args, **kwargs)
    return decorated_function

def create_jwt(payload):
    """
    Generates a JWT token signed with the app's SECRET_KEY.
    """
    try:
        # Ensure payload is a dict
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a dictionary.")

        # Add expiration if not present
        if 'exp' not in payload:
            # Default to 7 days
            payload['exp'] = datetime.utcnow() + timedelta(days=7)

        # Encode
        # PyJWT 2.0+ returns a string
        token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
        return token
    except Exception as e:
        current_app.logger.error(f"Error creating JWT: {e}")
        return None

def decode_jwt(token):
    """
    Decodes and validates a JWT token.
    Returns the payload dict if valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception as e:
        current_app.logger.error(f"Error decoding JWT: {e}")
        return None
