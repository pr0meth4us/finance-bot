import requests
import logging
from functools import wraps
from flask import request, jsonify, g, current_app
from requests.auth import HTTPBasicAuth
from cachetools import TTLCache

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
            # FIX: Safely attempt to parse JSON without using .is_json property
            try:
                err_resp = response.json()
            except ValueError:
                err_resp = {"error": response.text}

            current_app.logger.warning(f"Bifrost Validation Failed (401): {err_resp}")

            if "is_valid" in err_resp:
                # Auth succeeded, but Token is invalid
                return (True, err_resp, 200)
            else:
                # Basic Auth failed
                return (False, {"error": "Service Authentication Failed"}, 500)

        elif response.status_code == 403:
            return (False, response.json(), 403)

        else:
            current_app.logger.error(f"Bifrost unexpected status {response.status_code}: {response.text}")
            return (False, {"error": "Authentication service unavailable"}, 503)

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Bifrost Connection Error: {e}")
        return (False, {"error": "Authentication service connection error"}, 503)


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