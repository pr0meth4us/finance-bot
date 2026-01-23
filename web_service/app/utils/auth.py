# web_service/app/utils/auth.py

import os
import requests
import logging
from functools import wraps
from flask import request, jsonify, g
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
        # We assume Bifrost has an endpoint: GET /auth/api/verify?token=...
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


def auth_required(f):
    """
    Decorator to protect routes.
    Expects Bearer token in Authorization header.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Missing Authorization Header'}), 401

        try:
            token = auth_header.split(" ")[1]
        except IndexError:
            return jsonify({'error': 'Invalid Token Format'}), 401

        # 1. Validate token with Bifrost (Cached inside Bifrost or efficient check)
        bifrost_user = validate_bifrost_token(token)

        if not bifrost_user:
            return jsonify({'error': 'Invalid or Expired Token'}), 401

        # 2. Attach to Flask global context
        # We need to map Bifrost ID (account_id) to our local User
        account_id = bifrost_user.get('id')

        # Find local user by account_id
        user = User.find_by_account_id(account_id)

        if not user:
            # Fallback: Try finding by telegram_id if account_id missing (legacy)
            tg_id = bifrost_user.get('telegram_id')
            if tg_id:
                user = User.find_by_telegram_id(tg_id)

        if not user:
            # Lazy Provisioning: Create if doesn't exist yet
            # This handles cases where a user logs in via Web (Email) first
            log.info(f"Lazy provisioning user for account_id: {account_id}")
            user_data = {
                'account_id': account_id,
                'username': bifrost_user.get('username'),
                'telegram_id': bifrost_user.get('telegram_id'),
                'email': bifrost_user.get('email'),
                'role': bifrost_user.get('role', 'user')
            }
            # Only create if we have a valid identifier
            if account_id or user_data.get('telegram_id'):
                user = User.create_user(user_data)
            else:
                return jsonify({'error': 'User profile not found and cannot be provisioned'}), 404

        # Attach user object to g
        g.user = user
        g.bifrost_user = bifrost_user  # Keep the raw data just in case

        return f(*args, **kwargs)

    return decorated_function