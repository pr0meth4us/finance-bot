from flask import Blueprint, request, jsonify, current_app
import hmac
import hashlib
import json

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/verify-telegram', methods=['POST'])
def verify_telegram_auth():
    """Verifies the authentication data received from the Telegram Login Widget."""
    user_data = request.json

    if 'hash' not in user_data:
        return jsonify({'error': 'Hash not found in user data'}), 400

    # Get required environment variables
    bot_token = current_app.config.get('TELEGRAM_TOKEN')
    allowed_user_id = current_app.config.get('ALLOWED_USER_ID')

    if not bot_token or not allowed_user_id:
        return jsonify({'error': 'Server configuration missing for authentication'}), 500

    received_hash = user_data.pop('hash')

    # Create the data-check-string
    sorted_items = sorted(user_data.items())
    data_check_string = "\n".join([f"{k}={v}" for k, v in sorted_items])

    # Verify the hash
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if calculated_hash != received_hash:
        return jsonify({'error': 'Hash verification failed'}), 403

    # If hash is valid, check if the user is the allowed user
    if str(user_data.get('id')) != allowed_user_id:
        return jsonify({'error': 'User not authorized'}), 403

    # If both checks pass, the user is authenticated
    return jsonify({'status': 'ok', 'message': 'User authenticated successfully'})