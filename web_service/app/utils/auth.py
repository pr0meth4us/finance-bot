# web_service/app/utils/auth.py

import os
import requests
import logging
import jwt
from functools import wraps
from flask import request, jsonify, g, current_app
from requests.auth import HTTPBasicAuth

# Use local import to avoid circular dependency issues if User model imports auth
# from app.models import User (Moved inside function)

log = logging.getLogger(__name__)

BIFROST_URL = os.getenv("BIFROST_URL", "http://bifrost:5000")
BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID")
BIFROST_CLIENT_SECRET = os.getenv("BIFROST_CLIENT_SECRET")
BIFROST_TIMEOUT = 60


def validate_bifrost_token(token):
    """
    Validates the JWT with Bifrost using the Internal API.
    """
    if not token:
        return None

    if not BIFROST_CLIENT_ID or not BIFROST_CLIENT_SECRET:
        log.error("Bifrost Client ID/Secret not configured.")
        return None

    try:
        url = f"{BIFROST_URL}/internal/validate-token"
        auth = HTTPBasicAuth(BIFROST_CLIENT_ID, BIFROST_CLIENT_SECRET)
        payload = {"jwt": token}

        response = requests.post(url, json=payload, auth=auth, timeout=BIFROST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            if not data.get('is_valid'):
                return None

            # Return standardized user data
            return {
                'id': data.get('account_id'),
                'role': data.get('app_specific_role', 'user'),
                'email': data.get('email'),
                'username': data.get('username'),
                'telegram_id': data.get('telegram_id'),
                'display_name': data.get('display_name')
            }
        elif response.status_code == 401:
            log.warning("Bifrost rejected token.")
            return None
        else:
            log.error(f"Bifrost Error {response.status_code}: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        log.error(f"Error connecting to Bifrost: {e}")
        return None


def auth_required(min_role=None):
    """
    Core Decorator Logic.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({'message': 'Missing Authorization Header'}), 401

            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Invalid Token Format'}), 401

            # 1. Validate with Bifrost
            bifrost_user = validate_bifrost_token(token)
            if not bifrost_user:
                return jsonify({'message': 'Invalid or Expired Token'}), 401

            # 2. Extract Data
            account_id = bifrost_user.get('id')
            user_role = bifrost_user.get('role', 'user')

            # 3. Check Role (Strict 'premium_user' check)
            if min_role:
                # Hierarchy: user < premium_user < admin
                roles_hierarchy = ['user', 'premium_user', 'admin']

                # Check 1: Strict Equality (Fast path)
                if user_role == min_role:
                    pass
                # Check 2: Admin Override
                elif user_role == 'admin':
                    pass
                # Check 3: Hierarchy (Optional, but good for admin checks)
                else:
                    try:
                        u_idx = roles_hierarchy.index(user_role)
                        r_idx = roles_hierarchy.index(min_role)
                        if u_idx < r_idx:
                            return jsonify({'message': f'Required role: {min_role}'}), 403
                    except ValueError:
                        # Unknown role -> Deny
                        return jsonify({'message': 'Insufficient permissions'}), 403

            # 4. Load/Create Local User
            from app.models import User  # Late import to prevent circular deps
            user = User.get_by_account_id(account_id)

            if not user and bifrost_user.get('telegram_id'):
                user = User.find_by_telegram_id(bifrost_user.get('telegram_id'))

            if not user:
                log.info(f"Lazy provisioning user: {account_id}")
                user = User.create(
                    account_id=account_id,
                    role=user_role,
                    username=bifrost_user.get('username'),
                    email=bifrost_user.get('email'),
                    telegram_id=bifrost_user.get('telegram_id'),
                    display_name=bifrost_user.get('display_name')
                )

            # 5. Set Global Context
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


# ==========================================
# COMPATIBILITY ALIASES (Keep these!)
# ==========================================

def login_required(f):
    """Alias for @auth_required (no role check)"""
    return auth_required(min_role=None)(f)


def role_required(required_role):
    """Alias for @auth_required(min_role=...)"""
    return auth_required(min_role=required_role)


def service_auth_required(f):
    """Alias for Admin only"""
    return auth_required(min_role="admin")(f)


def get_token_from_header():
    """Helper used by some legacy utils"""
    auth_header = request.headers.get('Authorization')
    if auth_header:
        try:
            return auth_header.split(" ")[1]
        except IndexError:
            return None
    return None


def invalidate_token_cache(user_id):
    pass