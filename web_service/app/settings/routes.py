from flask import Blueprint, request, jsonify, g
from bson import ObjectId

from app.utils.db import settings_collection
from app.utils.auth import auth_required
from app.utils.currency import get_live_usd_to_khr_rate
from app.utils.serializers import serialize_profile

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


def get_account_id():
    try:
        return ObjectId(g.account_id)
    except Exception:
        raise ValueError('Invalid account_id format')


@settings_bp.route('/', methods=['GET'])
@auth_required(min_role="user")
def get_user_settings():
    try:
        account_id = get_account_id()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    user_settings = settings_collection().find_one(
        {'account_id': account_id},
        {'_id': 0, 'account_id': 1, 'settings': 1, 'name_en': 1, 'name_km': 1, 'onboarding_complete': 1}
    )

    if not user_settings:
        return jsonify({'error': 'User settings not found'}), 404

    return jsonify({"profile": serialize_profile(user_settings)})


@settings_bp.route('/balance', methods=['POST'])
@auth_required(min_role="user")
def update_initial_balance():
    try:
        account_id = get_account_id()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    data = request.json
    currency = str(data.get('currency', '')).upper()
    amount = data.get('amount')

    if not currency or amount is None:
        return jsonify({'error': 'Currency and amount are required'}), 400

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid amount format'}), 400

    update_key = f"settings.initial_balances.{currency}"
    result = settings_collection().update_one(
        {'account_id': account_id},
        {'$set': {update_key: amount}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User settings not found'}), 404

    return jsonify({'message': f'Initial balance for {currency} updated to {amount}'})


@settings_bp.route('/category', methods=['POST'])
@auth_required(min_role="premium_user")
def add_user_category():
    try:
        account_id = get_account_id()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    data = request.json
    cat_type = data.get('type')
    cat_name = data.get('name', '').strip().title()

    if cat_type not in ['expense', 'income']:
        return jsonify({'error': 'Invalid type'}), 400
    if not cat_name:
        return jsonify({'error': 'Category name cannot be empty'}), 400

    update_key = f"settings.categories.{cat_type}"
    result = settings_collection().update_one(
        {'account_id': account_id},
        {'$addToSet': {update_key: cat_name}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User settings not found'}), 404

    return jsonify({'message': f'Category "{cat_name}" added.'})


@settings_bp.route('/category', methods=['DELETE'])
@auth_required(min_role="premium_user")
def remove_user_category():
    try:
        account_id = get_account_id()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    data = request.json
    cat_type = data.get('type')
    cat_name = data.get('name')

    if cat_type not in ['expense', 'income']:
        return jsonify({'error': 'Invalid type'}), 400
    if not cat_name:
        return jsonify({'error': 'Category name required'}), 400

    update_key = f"settings.categories.{cat_type}"
    result = settings_collection().update_one(
        {'account_id': account_id},
        {'$pull': {update_key: cat_name}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User settings not found'}), 404
    if result.modified_count == 0:
        return jsonify({'error': 'Category not found or not removed'}), 400

    return jsonify({'message': f'Category "{cat_name}" removed.'})


@settings_bp.route('/rate', methods=['POST'])
@auth_required(min_role="user")
def update_khr_rate():
    try:
        account_id = get_account_id()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        new_rate = float(request.json.get('rate'))
    except (ValueError, TypeError):
        return jsonify({'error': 'Rate must be a number'}), 400

    settings_collection().update_one(
        {'account_id': account_id},
        {'$set': {
            'settings.rate_preference': 'fixed',
            'settings.fixed_rate': new_rate
        }}
    )

    return jsonify({'message': f'Exchange rate preference updated to fixed rate: {new_rate}'})


@settings_bp.route('/rate', methods=['GET'])
@auth_required(min_role="user")
def get_khr_rate():
    try:
        account_id = get_account_id()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    user_settings_doc = settings_collection().find_one({'account_id': account_id})
    if not user_settings_doc:
        return jsonify({'error': 'User settings not found'}), 404

    settings = user_settings_doc.get('settings', {})

    if settings.get('rate_preference') == 'fixed':
        return jsonify({'rate': settings.get('fixed_rate', 4100.0), 'source': 'fixed'})

    return jsonify({'rate': get_live_usd_to_khr_rate(), 'source': 'live'})


@settings_bp.route('/mode', methods=['POST'])
@auth_required(min_role="user")
def update_user_mode():
    try:
        account_id = get_account_id()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    data = request.json
    mode = data.get('mode')

    if mode not in ['single', 'dual']:
        return jsonify({'error': 'Invalid mode. Must be "single" or "dual".'}), 400

    update_payload = {'settings.currency_mode': mode}

    # Optional fields
    if 'name_en' in data:
        update_payload['name_en'] = data['name_en']
    if 'name_km' in data:
        update_payload['name_km'] = data['name_km']
    if 'language' in data:
        update_payload['settings.language'] = data['language']

    if mode == 'single':
        primary_curr = data.get('primary_currency')
        if not primary_curr:
            return jsonify({'error': 'primary_currency is required for single mode.'}), 400
        update_payload['settings.primary_currency'] = primary_curr.upper()
    elif mode == 'dual':
        # Ensure primary defaults to USD if switching to dual
        update_payload['settings.primary_currency'] = 'USD'

    result = settings_collection().update_one(
        {'account_id': account_id},
        {'$set': update_payload}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User settings not found'}), 404

    return jsonify({'message': 'User settings updated.'})


@settings_bp.route('/complete_onboarding', methods=['POST'])
@auth_required(min_role="user")
def complete_onboarding():
    try:
        account_id = get_account_id()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    result = settings_collection().update_one(
        {'account_id': account_id},
        {'$set': {'onboarding_complete': True}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User settings not found'}), 404

    return jsonify({'message': 'Onboarding complete.'})