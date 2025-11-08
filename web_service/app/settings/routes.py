# --- Start of modified file: web_service/app/settings/routes.py ---

from flask import Blueprint, request, jsonify
from app.utils.currency import get_live_usd_to_khr_rate
from app import get_db  # <-- IMPORT THE NEW FUNCTION

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


@settings_bp.route('/rate', methods=['POST'])
def update_khr_rate():
    data = request.json
    if 'rate' not in data:
        return jsonify({'error': 'Rate is required'}), 400

    try:
        new_rate = float(data['rate'])
    except ValueError:
        return jsonify({'error': 'Rate must be a number'}), 400

    db = get_db()  # <-- USE THE NEW FUNCTION
    db.settings.update_one(
        {'_id': 'config'},
        {'$set': {'khr_to_usd_rate': new_rate}},
        upsert=True
    )

    return jsonify({'message': f'Exchange rate updated to {new_rate}'})


@settings_bp.route('/rate', methods=['GET'])
def get_khr_rate():
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    """Fetches the current LIVE KHR to USD exchange rate."""

    # Call the utility function that fetches the live rate
    live_rate = get_live_usd_to_khr_rate()

    return jsonify({'rate': live_rate})