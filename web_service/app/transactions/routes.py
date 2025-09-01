from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from bson import ObjectId

transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

def serialize_tx(tx):
    tx['_id'] = str(tx['_id'])
    return tx

@transactions_bp.route('/', methods=['POST'])
def add_transaction():
    data = request.json
    if not all(k in data for k in ['type', 'amount', 'currency', 'categoryId', 'accountName']):
        return jsonify({'error': 'Missing required fields'}), 400

    tx = {
        "type": data['type'],
        "amount": float(data['amount']),
        "currency": data['currency'],
        "categoryId": data['categoryId'],
        "accountName": data['accountName'],
        "description": data.get('description', ''),
        "timestamp": datetime.utcnow()
    }
    result = current_app.db.transactions.insert_one(tx)
    return jsonify({'message': 'Transaction added', 'id': str(result.inserted_id)}), 201

@transactions_bp.route('/recent', methods=['GET'])
def get_recent_transactions():
    limit = int(request.args.get('limit', 5))
    txs = list(current_app.db.transactions.find().sort('timestamp', -1).limit(limit))
    return jsonify([serialize_tx(tx) for tx in txs])

@transactions_bp.route('/<tx_id>', methods=['DELETE'])
def delete_transaction(tx_id):
    result = current_app.db.transactions.delete_one({'_id': ObjectId(tx_id)})
    if result.deleted_count:
        return jsonify({'message': 'Transaction deleted'})
    return jsonify({'error': 'Transaction not found'}), 404