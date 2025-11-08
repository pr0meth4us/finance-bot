# --- Start of modified file: web_service/app/transactions/routes.py ---

from flask import Blueprint, request, jsonify
from datetime import datetime, time, timedelta
from bson import ObjectId
from app.utils.currency import get_live_usd_to_khr_rate
import re
from zoneinfo import ZoneInfo
from app import get_db  # <-- IMPORT THE NEW FUNCTION

transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")


# --- NEW: Helper to get user_id and check for it ---
def get_user_id_from_request():
    """
    Gets user_id from request.json or request.args.
    Returns (user_id, error_response)
    """
    user_id = None
    if request.is_json:
        user_id = request.json.get('user_id')

    if not user_id:
        user_id = request.args.get('user_id')

    if not user_id:
        return None, (jsonify({'error': 'user_id is required'}), 401) # 401 Unauthorized

    try:
        # Validate that it's a proper ObjectId
        return ObjectId(user_id), None
    except Exception:
        return None, (jsonify({'error': 'Invalid user_id format'}), 400)


def get_date_ranges_for_search():
    """Helper to get UTC date ranges for search queries."""
    today = datetime.now(PHNOM_PENH_TZ).date()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    end_of_last_week = start_of_week - timedelta(days=1)
    start_of_last_week = end_of_last_week - timedelta(days=6)

    def create_utc_range(start_local, end_local):
        aware_start = datetime.combine(start_local, time.min, tzinfo=PHNOM_PENH_TZ)
        aware_end = datetime.combine(end_local, time.max, tzinfo=PHNOM_PENH_TZ)
        return aware_start.astimezone(UTC_TZ), aware_end.astimezone(UTC_TZ)

    return {
        "today": create_utc_range(today, today),
        "this_week": create_utc_range(start_of_week, start_of_week + timedelta(days=6)),
        "last_week": create_utc_range(start_of_last_week, end_of_last_week),
        "this_month": create_utc_range(start_of_month,
                                       (start_of_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(
                                           days=1))
    }


def serialize_tx(tx):
    """
    Serializes a transaction document from MongoDB for JSON responses.
    Converts ObjectId and datetime to JSON-friendly string formats.
    """
    if '_id' in tx:
        tx['_id'] = str(tx['_id'])
    if 'timestamp' in tx and isinstance(tx['timestamp'], datetime):
        tx['timestamp'] = tx['timestamp'].isoformat()

    # --- MODIFICATION: Also serialize user_id if present ---
    if 'user_id' in tx:
        tx['user_id'] = str(tx['user_id'])

    return tx


@transactions_bp.route('/', methods=['POST'])
def add_transaction():
    """Adds a transaction for an authenticated user."""
    db = get_db()

    # --- MODIFICATION: Authenticate user ---
    user_id, error = get_user_id_from_request()
    if error: return error
    # ---

    data = request.json
    if not all(k in data for k in ['type', 'amount', 'currency', 'categoryId', 'accountName']):
        return jsonify({'error': 'Missing required fields'}), 400

    timestamp_str = data.get('timestamp')
    timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(UTC_TZ)

    tx = {
        "user_id": user_id, # <-- MODIFICATION: Add user_id
        "type": data['type'],
        "amount": float(data['amount']),
        "currency": data['currency'],
        "categoryId": data['categoryId'].strip().title(),
        "accountName": data['accountName'],
        "description": data.get('description', ''),
        "timestamp": timestamp
    }

    if tx['currency'] == 'KHR':
        tx['exchangeRateAtTime'] = get_live_usd_to_khr_rate()

    result = db.transactions.insert_one(tx)
    return jsonify({'message': 'Transaction added', 'id': str(result.inserted_id)}), 201


@transactions_bp.route('/recent', methods=['GET'])
def get_recent_transactions():
    """Fetches recent transactions for an authenticated user."""
    db = get_db()

    # --- MODIFICATION: Authenticate user ---
    user_id, error = get_user_id_from_request()
    if error: return error
    # ---

    limit = int(request.args.get('limit', 20))

    # --- MODIFICATION: Query is now user-specific ---
    txs = list(db.transactions.find({'user_id': user_id}).sort('timestamp', -1).limit(limit))
    # ---

    return jsonify([serialize_tx(tx) for tx in txs])


@transactions_bp.route('/search', methods=['POST'])
def search_transactions():
    """Performs an advanced search for an authenticated user."""
    params = request.json
    db = get_db()

    # --- MODIFICATION: Authenticate user ---
    user_id, error = get_user_id_from_request()
    if error: return error
    # ---

    # --- MODIFICATION: Add user_id to match_stage ---
    match_stage = {'user_id': user_id}
    # ---

    date_filter = {}
    if params.get('period'):
        ranges = get_date_ranges_for_search()
        if params['period'] in ranges:
            start_utc, end_utc = ranges[params['period']]
            date_filter['$gte'] = start_utc
            date_filter['$lte'] = end_utc
    elif params.get('start_date') and params.get('end_date'):
        start_local = datetime.fromisoformat(params['start_date']).date()
        end_local = datetime.fromisoformat(params['end_date']).date()
        aware_start = datetime.combine(start_local, time.min, tzinfo=PHNOM_PENH_TZ)
        aware_end = datetime.combine(end_local, time.max, tzinfo=PHNOM_PENH_TZ)
        date_filter['$gte'] = aware_start.astimezone(UTC_TZ)
        date_filter['$lte'] = aware_end.astimezone(UTC_TZ)

    if date_filter:
        match_stage['timestamp'] = date_filter

    if params.get('transaction_type'):
        match_stage['type'] = params['transaction_type']

    if params.get('categories'):
        categories_regex = [re.compile(f'^{re.escape(c.strip())}$', re.IGNORECASE) for c in params['categories']]
        match_stage['categoryId'] = {'$in': categories_regex}

    if params.get('keywords'):
        keywords = params['keywords']
        keyword_logic = params.get('keyword_logic', 'OR').upper()

        if keyword_logic == 'AND':
            match_stage['$and'] = [{'description': re.compile(k, re.IGNORECASE)} for k in keywords]
        else:
            regex_str = '|'.join([re.escape(k) for k in keywords])
            match_stage['description'] = re.compile(regex_str, re.IGNORECASE)

    results = list(db.transactions.find(match_stage).sort('timestamp', -1).limit(50))
    return jsonify([serialize_tx(tx) for tx in results])


@transactions_bp.route('/<tx_id>', methods=['GET'])
def get_transaction(tx_id):
    """Fetches a single transaction for an authenticated user."""
    db = get_db()

    # --- MODIFICATION: Authenticate user ---
    user_id, error = get_user_id_from_request()
    if error: return error
    # ---

    try:
        # --- MODIFICATION: Query is now user-specific ---
        transaction = db.transactions.find_one({'_id': ObjectId(tx_id), 'user_id': user_id})
        # ---

        if transaction:
            return jsonify(serialize_tx(transaction))
        else:
            return jsonify({'error': 'Transaction not found or access denied'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@transactions_bp.route('/<tx_id>', methods=['PUT'])
def update_transaction(tx_id):
    """Updates a transaction for an authenticated user."""
    data = request.json
    db = get_db()

    # --- MODIFICATION: Authenticate user ---
    user_id, error = get_user_id_from_request()
    if error: return error
    # ---

    if not data:
        return jsonify({'error': 'No update data provided'}), 400

    update_fields = {}
    allowed_fields = ['amount', 'categoryId', 'description', 'timestamp']

    for field in allowed_fields:
        if field in data:
            if field == 'amount':
                try:
                    update_fields[field] = float(data[field])
                except (ValueError, TypeError):
                    return jsonify({'error': 'Invalid amount format'}), 400
            elif field == 'categoryId':
                update_fields[field] = data[field].strip().title()
            elif field == 'timestamp':
                try:
                    update_fields[field] = datetime.fromisoformat(data[field])
                except (ValueError, TypeError):
                    return jsonify({'error': 'Invalid timestamp format'}), 400
            else:
                update_fields[field] = data[field]

    if not update_fields:
        return jsonify({'error': 'No valid fields to update'}), 400

    try:
        # --- MODIFICATION: Query is now user-specific ---
        result = db.transactions.update_one(
            {'_id': ObjectId(tx_id), 'user_id': user_id},
            {'$set': update_fields}
        )
        # ---

        if result.matched_count:
            return jsonify({'message': 'Transaction updated successfully'})
        else:
            return jsonify({'error': 'Transaction not found or access denied'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@transactions_bp.route('/<tx_id>', methods=['DELETE'])
def delete_transaction(tx_id):
    """Deletes a transaction for an authenticated user."""
    db = get_db()

    # --- MODIFICATION: Authenticate user ---
    # Note: user_id for DELETE comes from JSON body, not query param
    user_id, error = get_user_id_from_request()
    if error: return error
    # ---

    try:
        # --- MODIFICATION: Query is now user-specific ---
        result = db.transactions.delete_one({'_id': ObjectId(tx_id), 'user_id': user_id})
        # ---

        if result.deleted_count:
            return jsonify({'message': 'Transaction deleted'})
        else:
            return jsonify({'error': 'Transaction not found or access denied'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400
# --- End of modified file ---