# web_service/app/auth/routes.py

from flask import Blueprint, request, jsonify, current_app
from app.models import User
import requests
import os
from requests.auth import HTTPBasicAuth

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/sync-session', methods=['POST', 'OPTIONS'])
def sync_session():
    """
    Receives a Bifrost JWT in the Authorization header.
    Validates it with Bifrost Internal API.
    Ensures a local User record exists (JIT provisioning).
    """
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]

    # 1. Validate Token with Bifrost
    config = current_app.config
    bifrost_url = config.get("BIFROST_URL")
    client_id = config.get("BIFROST_CLIENT_ID")
    client_secret = config.get("BIFROST_CLIENT_SECRET")

    if not bifrost_url or not client_id or not client_secret:
        current_app.logger.error("Bifrost configuration missing in Web Service")
        return jsonify({"error": "Service misconfiguration"}), 500

    try:
        # Call Bifrost Introspection/Validation Endpoint
        # We perform a service-to-service call to ensure the token is valid
        # and to get the latest role/account info.
        res = requests.post(
            f"{bifrost_url}/internal/validate-token",
            json={"token": token},
            auth=HTTPBasicAuth(client_id, client_secret),
            timeout=10
        )

        if res.status_code != 200:
            return jsonify({"error": "Invalid token"}), 401

        data = res.json()
        if not data.get("is_valid"):
            return jsonify({"error": "Token expired or invalid"}), 401

        account_id = data.get("account_id")
        role = data.get("app_specific_role", "user")

        if not account_id:
            return jsonify({"error": "Token valid but missing account_id"}), 400

        # 2. Local Provisioning (Sync)
        user = User.get_by_account_id(account_id)
        if not user:
            # Create new local profile linked to Bifrost ID
            user = User.create(account_id, role=role)
        else:
            # Optionally sync role updates if stored locally
            user.update_role(role)

        return jsonify({
            "status": "success",
            "message": "Session synced",
            "local_id": str(user._id)
        }), 200

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Bifrost validation failed: {e}")
        return jsonify({"error": "Identity Provider unavailable"}), 503