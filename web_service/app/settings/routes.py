# --- web_service/app/settings/routes.py (Refactored) ---
"""
Handles user-specific settings.
All endpoints are multi-tenant and require a valid user_id.
"""
from flask import Blueprint, request, jsonify, g
from app.utils.currency import get_live_usd_to_khr_rate
from app.utils.db import settings_collection
# --- REFACTOR: Import new auth decorator ---
from app.utils.auth import auth_required

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


@settings_bp.route('/', methods=['GET'])
@auth_required(min_role="user")  # --- REFACTOR: Add decorator ---
def get_user_settings():
    """Fetches all settings for the authenticated user."""
    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    # --- REFACTOR: Use 'db.settings' and query by 'account_id' ---
    user_settings = settings_collection().find_one(
        {'account_id': account_id},
        {'_id': 0, 'settings': 1, 'name_en': 1, 'name_km': 1}
    )
    if not user_settings:
        return jsonify({'error': 'User settings not found'}), 404

    return jsonify(user_settings)


@settings_bp.route('/balance', methods=['POST'])
@auth_required(min_role="user")  # --- REFACTOR: Add decorator ---
def update_initial_balance():
    """Updates the initial balance for a specific currency for a user."""
    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    data = request.json
    if 'currency' not in data or 'amount' not in data:
        return jsonify({'error': 'Currency and amount are required'}), 400

    try:
        currency = str(data['currency']).upper()
        amount = float(data['amount'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid currency or amount format'}), 400

    update_key = f"settings.initial_balances.{currency}"
    # --- REFACTOR: Use 'db.settings' and query by 'account_id' ---
    result = settings_collection().update_one(
        {'account_id': account_id},
        {'$set': {update_key: amount}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User settings not found'}), 404

    return jsonify({
        'message': f'Initial balance for {currency} updated to {amount}'
    })


@settings_bp.route('/category', methods=['POST'])
@auth_required(min_role="premium_user")  # --- REFACTOR: Add decorator ---
def add_user_category():
    """Adds a new custom category for a user."""
    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

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
    # --- REFACTOR: Use 'db.settings' and query by 'account_id' ---
    result = settings_collection().update_one(
        {'account_id': account_id},
        {'$addToSet': {update_key: category_name}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User settings not found'}), 404

    return jsonify({
        'message': f'Category "{category_name}" added.'
    })


@settings_bp.route('/category', methods=['DELETE'])
@auth_required(min_role="premium_user")  # --- REFACTOR: Add decorator ---
def remove_user_category():
    """Removes a custom category for a user."""
    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    data = request.json
    if 'type' not in data or 'name' not in data:
        return jsonify({'error': 'Type (expense/income) and name are required'}), 400

    category_type = data['type']
    category_name = data['name']

    if category_type not in ['expense', 'income']:
        return jsonify({'error': 'Invalid type'}), 400

    update_key = f"settings.categories.{category_type}"
    # --- REFACTOR: Use 'db.settings' and query by 'account_id' ---
    result = settings_collection().update_one(
        {'account_id': account_id},
        {'$pull': {update_key: category_name}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User settings not found'}), 404

    if result.modified_count == 0:
        return jsonify({'error': 'Category not found or not removed'}), 400

    return jsonify({
        'message': f'Category "{category_name}" removed.'
    })


@settings_bp.route('/rate', methods=['POST'])
@auth_required(min_role="user")  # --- REFACTOR: Add decorator ---
def update_khr_rate():
    """Updates the user-specific fixed exchange rate."""
    data = request.json
    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    if 'rate' not in data:
        return jsonify({'error': 'Rate is required'}), 400

    try:
        new_rate = float(data['rate'])
    except ValueError:
        return jsonify({'error': 'Rate must be a number'}), 400

    # --- REFACTOR: Use 'db.settings' and query by 'account_id' ---
    settings_collection().update_one(
        {'account_id': account_id},
        {'$set': {
            'settings.rate_preference': 'fixed',
            'settings.fixed_rate': new_rate
        }}
    )

    return jsonify({
        'message': f'Exchange rate preference updated to fixed rate: {new_rate}'
    })


@settings_bp.route('/rate', methods=['GET'])
@auth_required(min_role="user")  # --- REFACTOR: Add decorator ---
def get_khr_rate():
    """
    Fetches the KHR exchange rate based on the user's preference.
    """
    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    # --- REFACTOR: Use 'db.settings' and query by 'account_id' ---
    user_settings_doc = settings_collection().find_one({'account_id': account_id})
    if not user_settings_doc:
        return jsonify({'error': 'User settings not found'}), 404

    user_settings = user_settings_doc.get('settings', {})
    preference = user_settings.get('rate_preference', 'live')

    if preference == 'fixed':
        fixed_rate = user_settings.get('fixed_rate', 4100.0)
        return jsonify({'rate': fixed_rate, 'source': 'fixed'})

    live_rate = get_live_usd_to_khr_rate()
    return jsonify({'rate': live_rate, 'source': 'live'})


@settings_bp.route('/mode', methods=['POST'])
@auth_required(min_role="user")  # --- REFACTOR: Add decorator ---
def update_user_mode():
    """
    Sets the user's currency mode, language, and names during onboarding.
    """
    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    data = request.json
    mode = data.get('mode')

    # --- REFACTOR: name_en is not required, name_km/language are optional ---
    name_en = data.get('name_en')
    name_km = data.get('name_km')
    language = data.get('language')

    if not mode or mode not in ['single', 'dual']:
        return jsonify({'error': 'Invalid mode. Must be "single" or "dual".'}), 400

    update_payload = {
        'settings.currency_mode': mode,
    }

    if name_en:
        update_payload['name_en'] = name_en
    if name_km:
        update_payload['name_km'] = name_km
    if language:
        update_payload['settings.language'] = language

    if mode == 'single':
        primary_currency = data.get('primary_currency')
        if not primary_currency:
            return jsonify({'error': 'primary_currency is required for single mode.'}), 400
        update_payload['settings.primary_currency'] = primary_currency.upper()

    elif mode == 'dual':
        # No longer require language/name_km, they can be set separately
        if 'settings.primary_currency' not in update_payload:
            update_payload['settings.primary_currency'] = 'USD'  # Default for dual

    # --- REFACTOR: Use 'db.settings' and query by 'account_id' ---
    result = settings_collection().update_one(
        {'account_id': account_id},
        {'$set': update_payload}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User settings not found'}), 404

    return jsonify({'message': f'User settings updated.'})


@settings_bp.route('/complete_onboarding', methods=['POST'])
@auth_required(min_role="user")  # --- REFACTOR: Add decorator ---
def complete_onboarding():
    """Marks the user's onboarding as complete."""
    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    # --- REFACTOR: Use 'db.settings' and query by 'account_id' ---
    result = settings_collection().update_one(
        {'account_id': account_id},
        {'$set': {'onboarding_complete': True}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User settings not found'}), 404

    return jsonify({'message': 'Onboarding complete.'})