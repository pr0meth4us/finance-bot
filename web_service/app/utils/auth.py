# --- web_service/app/utils/auth.py (Fixed) ---

import os
import requests
from functools import wraps
from flask import request, jsonify, g, current_app
from requests.auth import HTTPBasicAuth
from cachetools import TTLCache

# Cache validation results for 5 minutes (300 seconds) to reduce upstream API load
# Max size 1024 tokens
_token_cache = TTLCache(maxsize=1024, ttl=300)

# Define role hierarchy for gating
ROLE_HIERARCHY = {
    "user": 1,
    "premium_user": 2,
    "admin": 99  # Bifrost 'admin' role, not used for gating but good to have
}


def _get_role_level(role_name):
    """Returns the numerical level for a given role name."""
    return ROLE_HIERARCHY.get(role_name, 0)


def _validate_token_with_bifrost(token, bifrost_url, client_id, client_secret):
    """
    Validates token against Bifrost.
    Returns a tuple: (success_bool, data_dict_or_error_message, status_code)
    """
    # Check cache first
    if token in _token_cache:
        return _token_cache[token]

    validate_url = f"{bifrost_url}/internal/validate-token"
    payload = {"jwt": token}

    try:
        auth = HTTPBasicAuth(client_id, client_secret)
        response = requests.post(validate_url, auth=auth, json=payload, timeout=5)

        if response.status_code == 200:
            data = response.json()
            result = (True, data, 200)
            # Only cache successful or explicitly invalid token responses (not server errors)
            _token_cache[token] = result
            return result

        elif response.status_code == 401:
            return (False, {"error": "Authentication service auth failed"}, 500)

        elif response.status_code == 403:
            return (False, response.json(), 403)

        else:
            return (False, {"error": "Authentication service unavailable"}, 503)

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Could not connect to Bifrost: {e}", exc_info=True)
        return (False, {"error": "Authentication service connection error"}, 503)


def auth_required(min_role="user"):
    """
    Decorator to protect routes.
    Validates a JWT against the Bifrost /internal/validate-token endpoint.
    Populates g.account_id and g.role on success.
    Uses caching to avoid per-request external calls.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get("Authorization")
            token = None

            if not auth_header:
                return jsonify({"error": "Authorization header is missing"}), 401

            try:
                # Faster string split
                scheme, token = auth_header.split(maxsplit=1)
                if scheme.lower() != 'bearer':
                    return jsonify({"error": "Invalid Authorization header format"}), 401
            except ValueError:
                return jsonify({"error": "Invalid Authorization header format"}), 401

            # --- Server-to-Server Bifrost Call ---
            bifrost_url = current_app.config.get("BIFROST_URL")
            client_id = current_app.config.get("BIFROST_CLIENT_ID")
            client_secret = current_app.config.get("BIFROST_CLIENT_SECRET")

            if not bifrost_url or not client_id or not client_secret:
                current_app.logger.error("Bifrost env vars (URL, ID, SECRET) are not set.")
                return jsonify({"error": "Authentication system is misconfigured"}), 500

            # Perform validation (cached)
            success, data, status_code = _validate_token_with_bifrost(
                token, bifrost_url, client_id, client_secret
            )

            if success:
                if data.get("is_valid"):
                    # --- SUCCESS ---
                    user_role = data.get("app_specific_role", "user")
                    user_level = _get_role_level(user_role)
                    min_level = _get_role_level(min_role)

                    if user_level < min_level:
                        current_app.logger.warning(
                            f"Auth denied for {data.get('account_id')}: "
                            f"Role '{user_role}' < min_role '{min_role}'"
                        )
                        return jsonify({"error": "Forbidden: Insufficient role"}), 403

                    # Populate g for this request context
                    g.account_id = data.get("account_id")
                    g.role = user_role

                    return f(*args, **kwargs)
                else:
                    # Token processed but invalid
                    current_app.logger.warning(f"Bifrost validation failed: {data.get('error')}")
                    return jsonify({"error": "Invalid or expired token"}), 401

            # Failure in validation communication
            if "error" in data and status_code == 500:
                current_app.logger.error(f"Bifrost auth failed (401 upstream or config error): {data}")

            return jsonify(data), status_code

        return decorated_function

    return decorator