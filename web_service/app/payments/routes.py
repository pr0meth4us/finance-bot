from flask import Blueprint, request, jsonify, g, current_app
import requests
from requests.auth import HTTPBasicAuth
from app.utils.auth import auth_required

payments_bp = Blueprint('payments', __name__, url_prefix='/payments')

BIFROST_TIMEOUT = 60

@payments_bp.route('/checkout', methods=['POST', 'OPTIONS'])
@auth_required(min_role="user")
def create_checkout_session():
    # CORS Preflight
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response, 200

    try:
        account_id = g.account_id
    except Exception:
        return jsonify({'error': 'Invalid session'}), 400

    data = request.json

    # 1. Dynamic Product ID: Defaults to 'nmfmm' if not sent
    product_id = data.get('product_id', 'nmfmm')

    # 2. Provider Logic
    # We force 'gumroad' for the automated flow since ABA is manual now
    provider = 'gumroad'
    region = 'international'

    bifrost_payload = {
        "account_id": account_id,
        "amount": "5.00",
        "currency": "USD",
        "region": region,
        "target_role": "premium_user",
        "product_id": product_id,  # <--- Passes 'nmfmm' to Bifrost
        "email": getattr(g, 'email', None)
    }

    config = current_app.config
    bifrost_url = config["BIFROST_URL"].rstrip('/')
    target_url = f"{bifrost_url}/internal/payments/create-intent"

    try:
        auth = HTTPBasicAuth(config["BIFROST_CLIENT_ID"], config["BIFROST_CLIENT_SECRET"])
        response = requests.post(target_url, json=bifrost_payload, auth=auth, timeout=BIFROST_TIMEOUT)

        if response.status_code != 200:
            current_app.logger.error(f"Bifrost Payment Error: {response.text}")
            return jsonify({"error": "Payment initialization failed"}), response.status_code

        return jsonify(response.json())

    except Exception as e:
        current_app.logger.error(f"Payment Proxy Error: {e}")
        return jsonify({"error": "Internal service error"}), 500