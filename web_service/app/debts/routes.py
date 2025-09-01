from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from bson import ObjectId

debts_bp = Blueprint('debts', __name__, url_prefix='/debts')

def serialize_debt(doc):
    doc['_id'] = str(doc['_id'])
    return doc

@debts_bp.route('/', methods=['POST'])
def add_debt():
    data = request.json
    if not all(k in data for k in ['type', 'person', 'amount', 'currency']):
        return jsonify({'error': 'Missing required fields'}), 400

    debt = {
        "type": data['type'], # 'lent' or 'borrowed'
        "person": data['person'],
        "amount": float(data['amount']),
        "currency": data['currency'],
        "status": "open",
        "created_at": datetime.utcnow()
    }
    result = current_app.db.debts.insert_one(debt)
    return jsonify({'message': 'Debt recorded', 'id': str(result.inserted_id)}), 201

@debts_bp.route('/', methods=['GET'])
def get_open_debts():
    debts = list(current_app.db.debts.find({'status': 'open'}))
    return jsonify([serialize_debt(d) for d in debts])

@debts_bp.route('/<debt_id>/settle', methods=['POST'])
def settle_debt(debt_id):
    debt = current_app.db.debts.find_one({'_id': ObjectId(debt_id)})
    if not debt:
        return jsonify({'error': 'Debt not found'}), 404

    account_name = "USD Account" if debt['currency'] == "USD" else "KHR Account"

    tx = {
        "amount": debt['amount'],
        "currency": debt['currency'],
        "accountName": account_name,
        "timestamp": datetime.utcnow()
    }
    if debt['type'] == 'lent': # Someone paid you back
        tx['type'] = 'income'
        tx['categoryId'] = 'Debt Settled'
        tx['description'] = f"Repayment from {debt['person']}"
    else: # You paid someone back
        tx['type'] = 'expense'
        tx['categoryId'] = 'Debt Repayment'
        tx['description'] = f"Repayment to {debt['person']}"

    current_app.db.transactions.insert_one(tx)

    current_app.db.debts.update_one(
        {'_id': ObjectId(debt_id)},
        {'$set': {'status': 'settled', 'settled_at': datetime.utcnow()}}
    )

    return jsonify({'message': 'Debt has been settled and transaction recorded'})