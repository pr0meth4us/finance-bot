# --- Start of file: web_service/app/settings/routes.py ---
"""
Handles user-specific settings.
All endpoints are multi-tenant and require a valid user_id.
"""
from flask import Blueprint, request, jsonify
from app.utils.currency import get_live_usd_to_khr_rate
from app import get_db
from app.utils.auth import get_user_id_from_request

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


@settings_bp.route('/', methods=['GET'])
def get_user_settings():
    """Fetches all settings for the authenticated user."""
    db = get_db()
    user_id, error = get_user_id_from_request()
    if error:
        return error

    user = db.users.find_one({'_id': user_id}, {'_id': 0, 'settings': 1})
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify(user.get('settings', {}))


@settings_bp.route('/balance', methods=['POST'])
def update_initial_balance():
    """Updates the initial balance for a specific currency for a user."""
    db = get_db()
    user_id, error = get_user_id_from_request()
    if error:
        return error

    data = request.json
    if 'currency' not in data or 'amount' not in data:
        return jsonify({'error': 'Currency and amount are required'}), 400

    try:
        currency = str(data['currency']).upper()
        if currency not in ['USD', 'KHR']:
            raise ValueError("Invalid currency")
        amount = float(data['amount'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid currency or amount format'}), 400

    update_key = f"settings.initial_balances.{currency}"
    result = db.users.update_one(
        {'_id': user_id},
        {'$set': {update_key: amount}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'message': f'Initial balance for {currency} updated to {amount}'
    })


@settings_bp.route('/category', methods=['POST'])
def add_user_category():
    """Adds a new custom category for a user."""
    db = get_db()
    user_id, error = get_user_id_from_request()
    if error:
        return error

    data = request.json
    if 'type' not in data or 'name' not in data:
        return jsonify({'error': 'Type (expense/income) and name are required'}), 400

    category_type = data['type']
    category_name = data['name'].strip().title()

    if category_type not in ['expense', 'income']:
        return jsonify({'error': 'Invalid type'}), 400
    if not category_name:
        return jsonify({'error': 'Category name cannot be empty'}), 400

    update_key = f"settings.categories.{category_type}"
    result = db.users.update_one(
        {'_id': user_id},
        {'$addToSet': {update_key: category_name}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'message': f'Category "{category_name}" added.'
    })


@settings_bp.route('/category', methods=['DELETE'])
def remove_user_category():
    """Removes a custom category for a user."""
    db = get_db()
    user_id, error = get_user_id_from_request()
    if error:
        return error

    data = request.json
    if 'type' not in data or 'name' not in data:
        return jsonify({'error': 'Type (expense/income) and name are required'}), 400

    category_type = data['type']
    category_name = data['name']

    if category_type not in ['expense', 'income']:
        return jsonify({'error': 'Invalid type'}), 400

    update_key = f"settings.categories.{category_type}"
    result = db.users.update_one(
        {'_id': user_id},
        {'$pull': {update_key: category_name}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User not found'}), 404

    if result.modified_count == 0:
        return jsonify({'error': 'Category not found or not removed'}), 400

    return jsonify({
        'message': f'Category "{category_name}" removed.'
    })


@settings_bp.route('/rate', methods=['POST'])
def update_khr_rate():
    """Updates the user-specific fixed exchange rate."""
    data = request.json
    db = get_db()

    user_id, error = get_user_id_from_request()
    if error:
        return error

    if 'rate' not in data:
        return jsonify({'error': 'Rate is required'}), 400

    try:
        new_rate = float(data['rate'])
    except ValueError:
        return jsonify({'error': 'Rate must be a number'}), 400

    db.users.update_one(
        {'_id': user_id},
        {'$set': {
            'settings.rate_preference': 'fixed',
            'settings.fixed_rate': new_rate
        }}
    )

    return jsonify({
        'message': f'Exchange rate preference updated to fixed rate: {new_rate}'
    })


@settings_bp.route('/rate', methods=['GET'])
def get_khr_rate():
    """
    Fetches the KHR exchange rate based on the user's preference.
    """
    db = get_db()
    user_id, error = get_user_id_from_request()
    if error:
        return error

    user = db.users.find_one({'_id': user_id})
    if not user:
        return jsonify({'error': 'User not found'}), 404

    user_settings = user.get('settings', {})
    preference = user_settings.get('rate_preference', 'live')

    if preference == 'fixed':
        fixed_rate = user_settings.get('fixed_rate', 4100.0)
        return jsonify({'rate': fixed_rate, 'source': 'fixed'})

    live_rate = get_live_usd_to_khr_rate()
    return jsonify({'rate': live_rate, 'source': 'live'})


# --- NEW ENDPOINT ---
@settings_bp.route('/complete_onboarding', methods=['POST'])
def complete_onboarding():
    """Marks the user's onboarding as complete."""
    db = get_db()
    user_id, error = get_user_id_from_request()
    if error:
        return error

    result = db.users.update_one(
        {'_id': user_id},
        {'$set': {'onboarding_complete': True}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({'message': 'Onboarding complete.'})
# --- END NEW ENDPOINT ---

# --- End of file ---