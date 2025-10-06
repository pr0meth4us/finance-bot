from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from bson import ObjectId
from app.utils.currency import get_live_usd_to_khr_rate

transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')


def serialize_tx(tx):
    """
    Serializes a transaction document from MongoDB for JSON responses.
    Converts ObjectId and datetime to JSON-friendly string formats.
    """
    if '_id' in tx:
        tx['_id'] = str(tx['_id'])

    if 'timestamp' in tx and isinstance(tx['timestamp'], datetime):
        tx['timestamp'] = tx['timestamp'].isoformat()

    return tx


@transactions_bp.route('/', methods=['POST'])
def add_transaction():
    data = request.json
    if not all(k in data for k in ['type', 'amount', 'currency', 'categoryId', 'accountName']):
        return jsonify({'error': 'Missing required fields'}), 400

    timestamp_str = data.get('timestamp')
    if timestamp_str:
        timestamp = datetime.fromisoformat(timestamp_str)
    else:
        timestamp = datetime.utcnow()

    tx = {
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

    result = current_app.db.transactions.insert_one(tx)
    return jsonify({'message': 'Transaction added', 'id': str(result.inserted_id)}), 201


@transactions_bp.route('/recent', methods=['GET'])
def get_recent_transactions():
    limit = int(request.args.get('limit', 20))
    txs = list(current_app.db.transactions.find().sort('timestamp', -1).limit(limit))
    return jsonify([serialize_tx(tx) for tx in txs])


@transactions_bp.route('/<tx_id>', methods=['GET'])
def get_transaction(tx_id):
    try:
        transaction = current_app.db.transactions.find_one({'_id': ObjectId(tx_id)})
        if transaction:
            return jsonify(serialize_tx(transaction))
        else:
            return jsonify({'error': 'Transaction not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400


# --- START OF MODIFICATION ---
# New route to update an existing transaction
@transactions_bp.route('/<tx_id>', methods=['PUT'])
def update_transaction(tx_id):
    """Updates one or more fields of a specific transaction."""
    data = request.json
    if not data:
        return jsonify({'error': 'No update data provided'}), 400

    # Build the update payload dynamically
    update_fields = {}
    allowed_fields = ['amount', 'categoryId', 'description']
    for field in allowed_fields:
        if field in data:
            if field == 'amount':
                try:
                    update_fields[field] = float(data[field])
                except (ValueError, TypeError):
                    return jsonify({'error': 'Invalid amount format'}), 400
            elif field == 'categoryId':
                update_fields[field] = data[field].strip().title()
            else:
                update_fields[field] = data[field]

    if not update_fields:
        return jsonify({'error': 'No valid fields to update'}), 400

    try:
        result = current_app.db.transactions.update_one(
            {'_id': ObjectId(tx_id)},
            {'$set': update_fields}
        )
        if result.matched_count:
            return jsonify({'message': 'Transaction updated successfully'})
        else:
            return jsonify({'error': 'Transaction not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- END OF MODIFICATION ---


@transactions_bp.route('/<tx_id>', methods=['DELETE'])
def delete_transaction(tx_id):
    try:
        result = current_app.db.transactions.delete_one({'_id': ObjectId(tx_id)})
        if result.deleted_count:
            return jsonify({'message': 'Transaction deleted'})
        else:
            return jsonify({'error': 'Transaction not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400
