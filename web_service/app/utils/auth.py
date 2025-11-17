import requests
from functools import wraps
from flask import request, jsonify, g, current_app
from requests.auth import HTTPBasicAuth
from cachetools import TTLCache

# Cache validation results for 5 minutes (300 seconds)
# Max size 1024 tokens
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
    Returns: (success_bool, data_dict_or_error, status_code)
    """
    if token in _token_cache:
        return _token_cache[token]

    validate_url = f"{bifrost_url}/internal/validate-token"
    payload = {"jwt": token}

    try:
        auth = HTTPBasicAuth(client_id, client_secret)
        response = requests.post(validate_url, auth=auth, json=payload, timeout=5)

        if response.status_code == 200:
            result = (True, response.json(), 200)
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
    Decorator to protect routes using Bifrost JWT validation.
    Populates g.account_id and g.role on success.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return jsonify({"error": "Authorization header is missing"}), 401

            try:
                scheme, token = auth_header.split(maxsplit=1)
                if scheme.lower() != 'bearer':
                    raise ValueError("Invalid scheme")
            except ValueError:
                return jsonify({"error": "Invalid Authorization header format"}), 401

            # Config Check
            config = current_app.config
            if not all(
                    [config.get("BIFROST_URL"), config.get("BIFROST_CLIENT_ID"), config.get("BIFROST_CLIENT_SECRET")]):
                current_app.logger.error("Bifrost env vars are not set.")
                return jsonify({"error": "Authentication system is misconfigured"}), 500

            # Validate Token
            success, data, status_code = _validate_token_with_bifrost(
                token,
                config["BIFROST_URL"],
                config["BIFROST_CLIENT_ID"],
                config["BIFROST_CLIENT_SECRET"]
            )

            if not success:
                if "error" in data and status_code == 500:
                    current_app.logger.error(f"Bifrost auth failed: {data}")
                return jsonify(data), status_code

            if not data.get("is_valid"):
                current_app.logger.warning(f"Bifrost validation failed: {data.get('error')}")
                return jsonify({"error": "Invalid or expired token"}), 401

            # Check Role
            user_role = data.get("app_specific_role", "user")
            if _get_role_level(user_role) < _get_role_level(min_role):
                current_app.logger.warning(
                    f"Auth denied for {data.get('account_id')}: Role '{user_role}' < min_role '{min_role}'"
                )
                return jsonify({"error": "Forbidden: Insufficient role"}), 403

            # Context Setup
            g.account_id = data.get("account_id")
            g.role = user_role

            return f(*args, **kwargs)

        return decorated_function

    return decorator