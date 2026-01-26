# web_service/app/utils/auth.py

import os
import requests
import logging
import jwt
from functools import wraps
from flask import request, jsonify, g, current_app
from requests.auth import HTTPBasicAuth
from app.models import User

log = logging.getLogger(__name__)

BIFROST_URL = os.getenv("BIFROST_URL", "http://bifrost:5000")
BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID")
BIFROST_CLIENT_SECRET = os.getenv("BIFROST_CLIENT_SECRET")
BIFROST_TIMEOUT = 60


def validate_bifrost_token(token):
    """
    Validates the JWT with Bifrost using the Internal API.
    Ref: bifrost/internal/routes.py -> validate_token()
    """
    if not token:
        return None

    # Safety check for config
    if not BIFROST_CLIENT_ID or not BIFROST_CLIENT_SECRET:
        log.error("Bifrost Client ID/Secret not configured in Web Service.")
        return None

    try:
        # FIXED: Use the correct internal endpoint
        url = f"{BIFROST_URL}/internal/validate-token"

        # FIXED: Use Basic Auth (Service-to-Service)
        auth = HTTPBasicAuth(BIFROST_CLIENT_ID, BIFROST_CLIENT_SECRET)

        # FIXED: Send token in Body
        payload = {"jwt": token}

        response = requests.post(url, json=payload, auth=auth, timeout=BIFROST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()

            if not data.get('is_valid'):
                return None

            # Map Bifrost response to our User structure
            # Bifrost returns: { account_id, app_specific_role, email, username, telegram_id ... }
            user_data = {
                'id': data.get('account_id'),
                'role': data.get('app_specific_role', 'user'),
                'email': data.get('email'),
                'username': data.get('username'),
                'telegram_id': data.get('telegram_id'),
                'display_name': data.get('display_name')
            }
            return user_data

        elif response.status_code == 401:
            log.warning("Bifrost rejected the token (expired or invalid).")
            return None
        else:
            log.error(f"Bifrost Validation Error ({response.status_code}): {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        log.error(f"Error connecting to Bifrost: {e}")
        return None


def auth_required(min_role=None):
    """
    Decorator Factory to protect routes.

    Modes:
      1. @auth_required                 -> Validates login only.
      2. @auth_required(min_role='admin') -> Validates login AND role hierarchy.

    Populates:
      g.user (User object)
      g.account_id (Bifrost ID)
      g.role (current role)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({'error': 'Missing Authorization Header'}), 401

            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid Token Format'}), 401

            # 1. Validate token with Bifrost
            bifrost_user = validate_bifrost_token(token)

            if not bifrost_user:
                return jsonify({'error': 'Invalid or Expired Token'}), 401

            # 2. Extract Identity
            account_id = bifrost_user.get('id')
            user_role = bifrost_user.get('role', 'user')

            # 3. Role Hierarchy Check (if min_role specified)
            if min_role:
                roles_hierarchy = ['user', 'premium_user', 'admin']
                try:
                    user_idx = roles_hierarchy.index(user_role)
                    req_idx = roles_hierarchy.index(min_role)

                    if user_idx < req_idx:
                        return jsonify({
                            'error': f'Permission denied. Required: {min_role}, Current: {user_role}'
                        }), 403
                except ValueError:
                    # Fallback for unknown roles: Strict equality check + Admin override
                    if user_role != min_role and user_role != 'admin':
                        return jsonify({'error': 'Insufficient permissions'}), 403

            # 4. Find or Create Local User
            user = User.get_by_account_id(account_id)

            if not user:
                # Fallback: Try finding by telegram_id (Legacy Support)
                tg_id = bifrost_user.get('telegram_id')
                if tg_id:
                    user = User.find_by_telegram_id(tg_id)

            if not user:
                # Lazy Provisioning: Create profile on the fly
                log.info(f"Lazy provisioning user for account_id: {account_id}")
                user = User.create(
                    account_id=account_id,
                    role=user_role,
                    username=bifrost_user.get('username'),
                    email=bifrost_user.get('email'),
                    telegram_id=bifrost_user.get('telegram_id'),
                    display_name=bifrost_user.get('display_name')
                )

            if not user:
                return jsonify({'error': 'Failed to load user profile'}), 500

            # 5. Populate Global Context (Crucial for Routes)
            g.user = user
            g.account_id = account_id
            g.role = user_role
            g.email = bifrost_user.get('email')
            g.token = token # Useful for downstream calls

            return f(*args, **kwargs)
        return decorated_function

    # Magic to handle @auth_required without parentheses
    if callable(min_role):
        f = min_role
        min_role = None
        return decorator(f)

    return decorator


def service_auth_required(f):
    """
    Alias for admin-only routes.
    Used by app/auth/routes.py imports.
    """
    return auth_required(min_role="admin")(f)


def create_jwt(user_id, roles):
    """
    Local JWT creation helper.
    Required by app/auth/routes.py for local login flows.
    """
    payload = {
        'sub': user_id,
        'roles': roles
    }
    return jwt.encode(
        payload,
        current_app.config.get('SECRET_KEY', 'dev_secret'),
        algorithm='HS256'
    )


def decode_jwt(token):
    """
    Local JWT decode helper.
    """
    try:
        return jwt.decode(
            token,
            current_app.config.get('SECRET_KEY', 'dev_secret'),
            algorithms=['HS256']
        )
    except Exception:
        return None


def invalidate_token_cache(token):
    """
    Placeholder for token cache invalidation.
    Called by auth webhook when a user is banned or changes password.
    """
    # If using Redis, delete the key here.
    pass