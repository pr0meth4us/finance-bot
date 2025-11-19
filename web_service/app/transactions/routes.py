from flask import Blueprint, request, jsonify, g
from datetime import datetime, time, timedelta
from bson import ObjectId
from zoneinfo import ZoneInfo
import re

from app.utils.db import transactions_collection
from app.utils.auth import auth_required
from app.utils.currency import get_live_usd_to_khr_rate

transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")


def get_account_id():
    try:
        return ObjectId(g.account_id)
    except Exception:
        raise ValueError("Invalid account_id format")


def serialize_tx(tx):
    """Serializes a transaction document for JSON responses."""
    if not tx:
        return None
    if '_id' in tx:
        tx['_id'] = str(tx['_id'])
    if 'timestamp' in tx and isinstance(tx['timestamp'], datetime):
        tx['timestamp'] = tx['timestamp'].isoformat()
    if 'account_id' in tx:
        tx['account_id'] = str(tx['account_id'])
    return tx


def get_date_ranges_for_search():
    """Returns UTC date ranges for common search periods."""
    today = datetime.now(PHNOM_PENH_TZ).date()

    def to_utc_range(start, end):
        s = datetime.combine(start, time.min, tzinfo=PHNOM_PENH_TZ).astimezone(UTC_TZ)
        e = datetime.combine(end, time.max, tzinfo=PHNOM_PENH_TZ).astimezone(UTC_TZ)
        return s, e

    start_week = today - timedelta(days=today.weekday())
    start_month = today.replace(day=1)

    return {
        "today": to_utc_range(today, today),
        "this_week": to_utc_range(start_week, start_week + timedelta(days=6)),
        "last_week": to_utc_range(start_week - timedelta(days=7), start_week - timedelta(days=1)),
        "this_month": to_utc_range(
            start_month,
            (start_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        )
    }


@transactions_bp.route('/', methods=['POST'])
@auth_required(min_role="user")
def add_transaction():
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id format'}), 400

    data = request.json
    required = ['type', 'amount', 'currency', 'categoryId', 'accountName']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        timestamp = datetime.now(UTC_TZ)
        if data.get('timestamp'):
            timestamp = datetime.fromisoformat(data['timestamp'])

        tx = {
            "account_id": account_id,
            "type": data['type'],
            "amount": float(data['amount']),
            "currency": data['currency'],
            "categoryId": data['categoryId'].strip().title(),
            "accountName": data['accountName'],
            "description": data.get('description', ''),
            "timestamp": timestamp
        }
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid data format'}), 400

    if tx['currency'] == 'KHR':
        tx['exchangeRateAtTime'] = get_live_usd_to_khr_rate()

    result = transactions_collection().insert_one(tx)
    return jsonify({'message': 'Transaction added', 'id': str(result.inserted_id)}), 201


@transactions_bp.route('/recent', methods=['GET'])
@auth_required(min_role="user")
def get_recent_transactions():
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id format'}), 400

    limit = int(request.args.get('limit', 20))

    cursor = transactions_collection().find(
        {'account_id': account_id}
    ).sort('timestamp', -1).limit(limit)

    return jsonify([serialize_tx(tx) for tx in cursor])


@transactions_bp.route('/search', methods=['POST'])
@auth_required(min_role="user")
def search_transactions():
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id format'}), 400

    params = request.json
    match_stage = {'account_id': account_id}

    # Date Filtering
    date_filter = {}
    if params.get('period'):
        ranges = get_date_ranges_for_search()
        if params['period'] in ranges:
            s, e = ranges[params['period']]
            date_filter = {'$gte': s, '$lte': e}

    elif params.get('start_date') and params.get('end_date'):
        try:
            s_local = datetime.fromisoformat(params['start_date']).date()
            e_local = datetime.fromisoformat(params['end_date']).date()
            s_aware = datetime.combine(s_local, time.min, tzinfo=PHNOM_PENH_TZ).astimezone(UTC_TZ)
            e_aware = datetime.combine(e_local, time.max, tzinfo=PHNOM_PENH_TZ).astimezone(UTC_TZ)
            date_filter = {'$gte': s_aware, '$lte': e_aware}
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400

    if date_filter:
        match_stage['timestamp'] = date_filter

    # Type Filtering
    if params.get('transaction_type'):
        match_stage['type'] = params['transaction_type']

    # Category Filtering
    if params.get('categories'):
        # Compile regex once for efficiency
        cats = [re.compile(f'^{re.escape(c.strip())}$', re.IGNORECASE) for c in params['categories']]
        match_stage['categoryId'] = {'$in': cats}

    # Keyword Filtering
    if params.get('keywords'):
        keywords = params['keywords']
        logic = params.get('keyword_logic', 'OR').upper()

        if logic == 'AND':
            match_stage['$and'] = [{'description': re.compile(k, re.IGNORECASE)} for k in keywords]
        else:
            regex_str = '|'.join([re.escape(k) for k in keywords])
            match_stage['description'] = re.compile(regex_str, re.IGNORECASE)

    results = list(transactions_collection().find(match_stage).sort('timestamp', -1).limit(50))
    return jsonify([serialize_tx(tx) for tx in results])


@transactions_bp.route('/<tx_id>', methods=['GET'])
@auth_required(min_role="user")
def get_transaction(tx_id):
    try:
        account_id = get_account_id()
        tx = transactions_collection().find_one({'_id': ObjectId(tx_id), 'account_id': account_id})
        if not tx:
            return jsonify({'error': 'Transaction not found'}), 404
        return jsonify(serialize_tx(tx))
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@transactions_bp.route('/<tx_id>', methods=['PUT'])
@auth_required(min_role="user")
def update_transaction(tx_id):
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id format'}), 400

    data = request.json
    if not data:
        return jsonify({'error': 'No update data provided'}), 400

    update_fields = {}
    allowed = {'amount', 'categoryId', 'description', 'timestamp'}

    try:
        if 'amount' in data:
            update_fields['amount'] = float(data['amount'])
        if 'categoryId' in data:
            update_fields['categoryId'] = data['categoryId'].strip().title()
        if 'description' in data:
            update_fields['description'] = data['description']
        if 'timestamp' in data:
            update_fields['timestamp'] = datetime.fromisoformat(data['timestamp'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid data format'}), 400

    if not update_fields:
        return jsonify({'error': 'No valid fields to update'}), 400

    result = transactions_collection().update_one(
        {'_id': ObjectId(tx_id), 'account_id': account_id},
        {'$set': update_fields}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'Transaction not found or access denied'}), 404

    return jsonify({'message': 'Transaction updated successfully'})


@transactions_bp.route('/<tx_id>', methods=['DELETE'])
@auth_required(min_role="user")
def delete_transaction(tx_id):
    try:
        account_id = get_account_id()
        result = transactions_collection().delete_one({'_id': ObjectId(tx_id), 'account_id': account_id})

        if result.deleted_count == 0:
            return jsonify({'error': 'Transaction not found'}), 404

        return jsonify({'message': 'Transaction deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400