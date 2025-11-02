from flask import Blueprint, request, jsonify, current_app

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

    current_app.db.settings.update_one(
        {'_id': 'config'},
        {'$set': {'khr_to_usd_rate': new_rate}},
        upsert=True
    )

    return jsonify({'message': f'Exchange rate updated to {new_rate}'})


# --- NEW FUNCTION ---
@settings_bp.route('/rate', methods=['GET'])
def get_khr_rate():
    """Fetches the currently stored KHR to USD exchange rate."""
    settings = current_app.db.settings.find_one({'_id': 'config'})

    if settings and 'khr_to_usd_rate' in settings:
        rate = float(settings['khr_to_usd_rate'])
    else:
        rate = 4100.0  # Default fallback

    return jsonify({'rate': rate})