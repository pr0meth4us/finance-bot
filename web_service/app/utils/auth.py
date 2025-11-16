# --- web_service/app/utils/auth.py (Fixed) ---

import os
import requests
from functools import wraps
from flask import request, jsonify, g, current_app
from requests.auth import HTTPBasicAuth

# Define role hierarchy for gating
ROLE_HIERARCHY = {
    "user": 1,
    "premium_user": 2,
    "admin": 99  # Bifrost 'admin' role, not used for gating but good to have
}


def _get_role_level(role_name):
    """Returns the numerical level for a given role name."""
    return ROLE_HIERARCHY.get(role_name, 0)


def auth_required(min_role="user"):
    """
    Decorator to protect routes.
    Validates a JWT against the Bifrost /internal/validate-token endpoint.
    Populates g.account_id and g.role on success.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get("Authorization")
            token = None

            if not auth_header:
                return jsonify({"error": "Authorization header is missing"}), 401

            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]

            if not token:
                return jsonify({"error": "Invalid Authorization header format"}), 401

            # --- Server-to-Server Bifrost Call ---
            bifrost_url = current_app.config.get("BIFROST_URL")
            client_id = current_app.config.get("BIFROST_CLIENT_ID")
            client_secret = current_app.config.get("BIFROST_CLIENT_SECRET")

            if not bifrost_url or not client_id or not client_secret:
                current_app.logger.error("Bifrost env vars (URL, ID, SECRET) are not set.")
                return jsonify({"error": "Authentication system is misconfigured"}), 500

            validate_url = f"{bifrost_url}/internal/validate-token"

            try:
                # Authenticate this service (FinanceBot) to Bifrost using Basic Auth
                auth = HTTPBasicAuth(client_id, client_secret)

                # Send the *user's* JWT in the payload to be validated
                payload = {"jwt": token}

                response = requests.post(validate_url, auth=auth, json=payload, timeout=5)

                if response.status_code == 200:
                    data = response.json()
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

                        # --- THIS IS THE FIX ---
                        # We no longer need telegram_id, as Bifrost doesn't send it
                        # g.telegram_id = data.get("telegram_id")
                        # --- END FIX ---

                        return f(*args, **kwargs)

                    else:
                        # Token was processed but found invalid
                        current_app.logger.warning(f"Bifrost validation failed: {data.get('error')}")
                        return jsonify({"error": "Invalid or expired token"}), 401

                elif response.status_code == 401:
                    # Error with *this service's* credentials
                    current_app.logger.error("Bifrost auth failed (401). Check CLIENT_ID/SECRET.")
                    return jsonify({"error": "Authentication service auth failed"}), 500

                elif response.status_code == 403:
                    # This happens if the account is not linked to the app
                    current_app.logger.error(f"Bifrost validation error 403: {response.text}")
                    return jsonify(response.json()), 403

                else:
                    # Other Bifrost error
                    current_app.logger.error(f"Bifrost error {response.status_code}: {response.text}")
                    return jsonify({"error": "Authentication service unavailable"}), 503

            except requests.exceptions.RequestException as e:
                current_app.logger.error(f"Could not connect to Bifrost: {e}", exc_info=True)
                return jsonify({"error": "Authentication service connection error"}), 503

        return decorated_function

    return decorator