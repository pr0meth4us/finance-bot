# web_service/app/utils/auth.py

import os
import requests
import logging
import jwt
from functools import wraps
from flask import request, jsonify, g, current_app
from app.models import User

log = logging.getLogger(__name__)

BIFROST_URL = os.getenv("BIFROST_URL", "http://bifrost:5000")
# Dedicated timeout for Bifrost calls (60s)
BIFROST_TIMEOUT = 60


def validate_bifrost_token(token):
    """
    Validates the JWT with Bifrost.
    Returns the user data (dict) if valid, None otherwise.
    """
    if not token:
        return None

    try:
        # Call Bifrost to validate
        url = f"{BIFROST_URL}/auth/api/verify"
        response = requests.get(
            url,
            params={"token": token},
            timeout=BIFROST_TIMEOUT
        )

        if response.status_code == 200:
            return response.json().get('user')
        else:
            log.warning(f"Bifrost token validation failed: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        log.error(f"Error connecting to Bifrost for token validation: {e}")
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
            # FIXED: Uses User.get_by_account_id (was find_by_account_id)
            user = User.get_by_account_id(account_id)

            if not user:
                # Fallback: Try finding by telegram_id (Legacy Support)
                tg_id = bifrost_user.get('telegram_id')
                if tg_id:
                    user = User.find_by_telegram_id(tg_id)

            if not user:
                # Lazy Provisioning: Create profile on the fly
                log.info(f"Lazy provisioning user for account_id: {account_id}")
                # FIXED: Uses User.create (was create_user)
                user = User.create(
                    account_id=account_id,
                    role=user_role,
                    username=bifrost_user.get('username'),
                    email=bifrost_user.get('email'),
                    telegram_id=bifrost_user.get('telegram_id')
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