import requests
import logging
from functools import wraps
from flask import request, jsonify, g
from requests.auth import HTTPBasicAuth
from app.config import Config

log = logging.getLogger(__name__)


def validate_bifrost_token(token):
    """
    Asks Bifrost: "Is this token valid?"
    Uses Basic Auth to authenticate the Service (Finance Bot) itself.
    """
    if not Config.BIFROST_CLIENT_ID or not Config.BIFROST_CLIENT_SECRET:
        log.error("CRITICAL: BIFROST_CLIENT_ID or BIFROST_CLIENT_SECRET is missing in environment!")
        return None

    if not token:
        return None

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

            return {
                'id': data.get('account_id'),
                'role': data.get('app_specific_role', 'user'),
                'email': data.get('email'),
                'username': data.get('username'),
                'telegram_id': data.get('telegram_id'),
                'display_name': data.get('display_name')
            }

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


# --- Aliases for Backward Compatibility ---
def login_required(f):
    return auth_required(min_role='user')(f)


def role_required(required_role):
    return auth_required(min_role=required_role)


def service_auth_required(f):
    return auth_required(min_role="admin")(f)


def invalidate_token_cache(token):
    pass