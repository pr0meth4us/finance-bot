# --- Start of modified file: web_service/app/settings/routes.py ---
"""
Handles user-specific settings.
All endpoints are multi-tenant and require a valid user_id.
"""
from flask import Blueprint, request, jsonify
from app.utils.currency import get_live_usd_to_khr_rate
from app import get_db
# --- MODIFICATION: Import the new auth helper ---
from app.utils.auth import get_user_id_from_request

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


@settings_bp.route('/rate', methods=['POST'])
def update_khr_rate():
    """Updates the user-specific fixed exchange rate."""
    data = request.json
    db = get_db()

    # --- MODIFICATION: Authenticate user ---
    user_id, error = get_user_id_from_request()
    if error: return error
    # ---

    if 'rate' not in data:
        return jsonify({'error': 'Rate is required'}), 400

    try:
        new_rate = float(data['rate'])
    except ValueError:
        return jsonify({'error': 'Rate must be a number'}), 400

    # --- MODIFICATION: Update the user's settings document ---
    db.users.update_one(
        {'_id': user_id},
        {'$set': {
            'settings.rate_preference': 'fixed',
            'settings.fixed_rate': new_rate
        }}
    )
    # ---

    return jsonify({'message': f'Exchange rate preference updated to fixed rate: {new_rate}'})


@settings_bp.route('/rate', methods=['GET'])
def get_khr_rate():
    """
    Fetches the KHR exchange rate based on the user's preference (live or fixed).
    """
    db = get_db()

    # --- MODIFICATION: Authenticate user ---
    user_id, error = get_user_id_from_request()
    if error: return error
    # ---

    # --- MODIFICATION: Fetch user's settings ---
    user = db.users.find_one({'_id': user_id})
    if not user:
        return jsonify({'error': 'User not found'}), 404

    user_settings = user.get('settings', {})
    preference = user_settings.get('rate_preference', 'live')
    # ---

    if preference == 'fixed':
        fixed_rate = user_settings.get('fixed_rate', 4100.0)
        return jsonify({'rate': fixed_rate, 'source': 'fixed'})

    # Default is 'live'
    live_rate = get_live_usd_to_khr_rate()
    return jsonify({'rate': live_rate, 'source': 'live'})
# --- End of modified file ---