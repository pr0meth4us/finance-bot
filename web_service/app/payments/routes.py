from flask import Blueprint, request, jsonify, g, current_app
from bson import ObjectId
import requests
from requests.auth import HTTPBasicAuth

from app.utils.auth import auth_required

payments_bp = Blueprint('payments', __name__, url_prefix='/payments')


@payments_bp.route('/checkout', methods=['POST'])
@auth_required(min_role="user")
def create_checkout_session():
    """
    Proxies a payment request to Bifrost.
    Payload: { "provider": "gumroad" | "payway", "product_id": "savvify-premium" }
    """
    try:
        account_id = g.account_id  # From auth decorator
    except Exception:
        return jsonify({'error': 'Invalid session'}), 400

    data = request.json
    provider = data.get('provider', 'payway')  # Default to local
    product_id = data.get('product_id', 'savvify-premium')

    # Define Bifrost "Region" based on provider choice
    region = 'international' if provider == 'gumroad' else 'local'

    # Prepare payload for Bifrost
    bifrost_payload = {
        "account_id": account_id,
        "amount": "5.00",  # Hardcoded for V1, or dynamic based on product_id
        "currency": "USD",
        "region": region,
        "target_role": "premium_user",
        "product_id": product_id,

        # Pass user info for invoicing if available (optional)
        "email": getattr(g, 'email', None)
    }

    # Call Bifrost (Server-to-Server)
    config = current_app.config
    bifrost_url = config["BIFROST_URL"].rstrip('/')
    target_url = f"{bifrost_url}/internal/payments/create-intent"

    try:
        # Use Client Credentials to authenticate with Bifrost
        auth = HTTPBasicAuth(config["BIFROST_CLIENT_ID"], config["BIFROST_CLIENT_SECRET"])

        # Increase timeout for external API calls
        response = requests.post(target_url, json=bifrost_payload, auth=auth, timeout=30)

        if response.status_code != 200:
            current_app.logger.error(f"Bifrost Payment Error: {response.text}")
            return jsonify({"error": "Payment initialization failed"}), response.status_code

        return jsonify(response.json())

    except Exception as e:
        current_app.logger.error(f"Payment Proxy Error: {e}")
        return jsonify({"error": "Internal service error"}), 500