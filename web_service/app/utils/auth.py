# web_service/app/utils/auth.py
import requests
import logging
import time
from functools import wraps
from flask import request, jsonify, g
from requests.auth import HTTPBasicAuth
from app.config import Config

log = logging.getLogger(__name__)

# In-memory token storage: { "token": {"data": user_data, "expires_at": timestamp} }
_TOKEN_CACHE = {}
TOKEN_TTL = 24 * 60 * 60  # 24 hours in seconds

def get_cached_token_data(token):
    cache_entry = _TOKEN_CACHE.get(token)
    if cache_entry:
        if time.time() < cache_entry["expires_at"]:
            return cache_entry["data"]
        else:
            _TOKEN_CACHE.pop(token, None)
    return None

def set_cached_token_data(token, user_data):
    # Basic cleanup to prevent memory leaks if the cache grows too large
    if len(_TOKEN_CACHE) > 1000:
        now = time.time()
        expired = [k for k, v in _TOKEN_CACHE.items() if v['expires_at'] < now]
        for k in expired:
            _TOKEN_CACHE.pop(k, None)

    _TOKEN_CACHE[token] = {
        "data": user_data,
        "expires_at": time.time() + TOKEN_TTL
    }

def invalidate_token_cache(token):
    """Removes a token from the cache (e.g., upon logout or webhook event)."""
    _TOKEN_CACHE.pop(token, None)

def invalidate_token_cache_by_account(account_id):
    """Removes all cached tokens for a specific account ID."""
    to_remove = []
    account_id_str = str(account_id)
    for token, cache_entry in _TOKEN_CACHE.items():
        if str(cache_entry["data"].get("id")) == account_id_str:
            to_remove.append(token)
    for token in to_remove:
        _TOKEN_CACHE.pop(token, None)

def validate_bifrost_token(token):
    """
    Asks Bifrost: "Is this token valid?"
    Uses Basic Auth to authenticate the Service (Finance Bot) itself.
    """
    if not Config.BIFROST_CLIENT_ID or not Config.BIFROST_CLIENT_SECRET:
        log.error("CRITICAL: BIFROST_CLIENT_ID or BIFROST_CLIENT_SECRET missing.")
        return None

    if not token:
        return None

    cached_data = get_cached_token_data(token)
    if cached_data:
        return cached_data

    try:
        url = f"{Config.BIFROST_URL}/internal/validate-token"
        auth = HTTPBasicAuth(Config.BIFROST_CLIENT_ID, Config.BIFROST_CLIENT_SECRET)
        payload = {"jwt": token}

        response = requests.post(url, json=payload, auth=auth, timeout=Config.BIFROST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            if not data.get('is_valid'):
                log.warning(f"Bifrost rejected token. Reason: {data.get('reason', 'Unknown')}")
                return None

            user_data = {
                'id': data.get('account_id'),
                'role': data.get('app_specific_role', 'user'),
                'email': data.get('email'),
                'username': data.get('username'),
                'telegram_id': data.get('telegram_id'),
                'display_name': data.get('display_name')
            }
            set_cached_token_data(token, user_data)
            return user_data

        log.error(f"Bifrost Validation Failed. HTTP {response.status_code}: {response.text}")
        return None

    except requests.exceptions.ConnectionError:
        log.error(f"Could not connect to Bifrost at {Config.BIFROST_URL}. Is the service running?")
        return None
    except Exception as e:
        log.error(f"Unexpected error validating Bifrost token: {e}")
        return None

def auth_required(min_role=None):
    """
    Authenticates requests using Bifrost Tokens.
    Enforces Role Hierarchy (Admin > Premium > User).
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({'message': 'Missing Authorization Header'}), 401

            # Robust Token Extraction: Handle "Bearer <token>" and raw "<token>"
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
            elif len(parts) == 1:
                token = parts[0]
            else:
                return jsonify({'message': 'Invalid Token Format'}), 401

            # 1. Validate with Bifrost
            bifrost_user = validate_bifrost_token(token)
            if not bifrost_user:
                return jsonify({'message': 'Invalid or Expired Bifrost Token'}), 401

            # 2. Lazy Provisioning (Sync Local DB)
            from app.models import User
            account_id = bifrost_user.get('id')
            user = User.get_by_account_id(account_id)
            if not user:
                log.info(f"Provisioning local user for Bifrost Account: {account_id}")
                user = User.create(
                    account_id=account_id,
                    role=bifrost_user.get('role', 'user'),
                    username=bifrost_user.get('username'),
                    email=bifrost_user.get('email'),
                    telegram_id=bifrost_user.get('telegram_id'),
                    display_name=bifrost_user.get('display_name')
                )

            # 3. Role Hierarchy Check
            user_role = bifrost_user.get('role', 'user')
            if min_role:
                # Use ROLE_LEVELS from config
                u_lvl = Config.ROLE_LEVELS.get(user_role, 0)
                r_lvl = Config.ROLE_LEVELS.get(min_role, 99)

                # Special Case: Admin passes everything
                if user_role == 'admin':
                    pass
                # Standard Check: Current Level must be >= Required Level
                elif u_lvl < r_lvl:
                    return jsonify({
                        'message': f'Forbidden: Requires {min_role} (Current: {user_role})'
                    }), 403

            # 4. Set Context
            g.user = user
            g.account_id = account_id
            g.role = user_role
            g.email = bifrost_user.get('email')

            return f(*args, **kwargs)
        return decorated_function
    if callable(min_role):
        f = min_role
        min_role = None
        return decorator(f)
    return decorator

def login_required(f):
    """Legacy alias for @auth_required()"""
    return auth_required()(f)

def role_required(min_role):
    """Legacy alias for @auth_required(min_role=X)"""
    return auth_required(min_role)

def service_auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Service auth logic
        return f(*args, **kwargs)
    return decorated_function