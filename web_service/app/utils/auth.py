# web_service/app/utils/auth.py

import os
import requests
import logging
from functools import wraps
from flask import request, jsonify, g, current_app
from requests.auth import HTTPBasicAuth

log = logging.getLogger(__name__)

BIFROST_URL = os.getenv("BIFROST_URL", "http://bifrost:5000")
BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID")
BIFROST_CLIENT_SECRET = os.getenv("BIFROST_CLIENT_SECRET")
BIFROST_TIMEOUT = 60


def validate_bifrost_token(token):
    """
    Asks Bifrost: "Is this token valid?"
    """
    if not token or not BIFROST_CLIENT_ID:
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

            return {
                'id': data.get('account_id'),
                'role': data.get('app_specific_role', 'user'),
                'email': data.get('email'),
                'username': data.get('username'),
                'telegram_id': data.get('telegram_id'),
                'display_name': data.get('display_name')
            }
        return None
    except Exception as e:
        log.error(f"Error connecting to Bifrost: {e}")
        return None


def auth_required(min_role=None):
    """
    Authenticates requests using ONLY Bifrost Tokens.
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

            # 3. Role Check
            user_role = bifrost_user.get('role', 'user')
            if min_role:
                if user_role != min_role and user_role != 'admin':
                    return jsonify({'message': f'Forbidden: Requires {min_role}'}), 403

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


# --- Aliases for Backward Compatibility ---
def login_required(f):
    return auth_required(min_role=None)(f)


def role_required(required_role):
    return auth_required(min_role=required_role)


def service_auth_required(f):
    return auth_required(min_role="admin")(f)


def invalidate_token_cache(token):
    pass