# --- File: web_service/app/debts/routes.py ---

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

    try:
        amount = float(data['amount'])
    except ValueError:
        return jsonify({'error': 'Amount must be a number'}), 400

    timestamp_str = data.get('timestamp')
    try:
        created_at = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.utcnow()
    except ValueError:
        created_at = datetime.utcnow()

    debt = {
        "type": data['type'],
        "person": data['person'],
        "originalAmount": amount,
        "remainingAmount": amount,
        "currency": data['currency'],
        "status": "open",
        "purpose": data.get("purpose", ""),
        "repayments": [],
        "created_at": created_at
    }

    account_name = "USD Account" if data['currency'] == "USD" else "KHR Account"
    tx_data = {
        "amount": amount,
        "currency": data['currency'],
        "accountName": account_name,
        "timestamp": created_at,
        "description": f"Loan {data['type']} {data['person']}"
    }

    if data['type'] == 'lent':
        tx_data['type'] = 'expense'
        tx_data['categoryId'] = 'Loan Lent'
    else: # type == 'borrowed'
        tx_data['type'] = 'income'
        tx_data['categoryId'] = 'Loan Received'

    current_app.db.transactions.insert_one(tx_data)
    result = current_app.db.debts.insert_one(debt)
    return jsonify({'message': 'Debt recorded', 'id': str(result.inserted_id)}), 201

# --- START OF MODIFICATION ---
@debts_bp.route('/', methods=['GET'])
def get_open_debts():
    """
    Fetches open debts and groups them by person and currency to provide a summary.
    This matches the expectation of the frontend keyboard `iou_list_keyboard`.
    """
    pipeline = [
        {'$match': {'status': 'open'}},
        {
            '$group': {
                '_id': {
                    'person': '$person',
                    'currency': '$currency',
                    'type': '$type'
                },
                'totalAmount': {'$sum': '$remainingAmount'}, # Key expected by frontend
                'count': {'$sum': 1}                     # Key expected by frontend
            }
        },
        {
            '$project': {
                '_id': 0,
                'person': '$_id.person',
                'currency': '$_id.currency',
                'type': '$_id.type',
                'totalAmount': '$totalAmount',
                'count': '$count'
            }
        },
        {'$sort': {'person': 1}}
    ]
    grouped_debts = list(current_app.db.debts.aggregate(pipeline))
    return jsonify(grouped_debts)
# --- END OF MODIFICATION ---

@debts_bp.route('/<debt_id>', methods=['GET'])
def get_debt_details(debt_id):
    debt = current_app.db.debts.find_one({'_id': ObjectId(debt_id)})
    if not debt:
        return jsonify({'error': 'Debt not found'}), 404
    return jsonify(serialize_debt(doc))

@debts_bp.route('/person/<person_name>/<currency>', methods=['GET'])
def get_debts_by_person_and_currency(person_name, currency):
    query_filter = {
        'person': person_name,
        'currency': currency,
        'status': 'open'
    }
    debts = list(current_app.db.debts.find(query_filter).sort('created_at', 1))
    return jsonify([serialize_debt(d) for d in debts])

@debts_bp.route('/<debt_id>/repay', methods=['POST'])
def record_repayment(debt_id):
    data = request.json
    if 'amount' not in data:
        return jsonify({'error': 'Repayment amount is required'}), 400

    try:
        repayment_amount = float(data['amount'])
    except ValueError:
        return jsonify({'error': 'Amount must be a number'}), 400

    debt = current_app.db.debts.find_one({'_id': ObjectId(debt_id)})
    if not debt:
        return jsonify({'error': 'Debt not found'}), 404

    if repayment_amount > debt['remainingAmount'] + 0.001:
        return jsonify({'error': f"Repayment ({repayment_amount}) cannot be greater than the remaining amount ({debt['remainingAmount']})"}), 400

    account_name = "USD Account" if debt['currency'] == "USD" else "KHR Account"
    tx = {
        "amount": repayment_amount,
        "currency": debt['currency'],
        "accountName": account_name,
        "timestamp": datetime.utcnow()
    }
    if debt['type'] == 'lent':
        tx['type'] = 'income'
        tx['categoryId'] = 'Debt Settled'
        tx['description'] = f"Repayment from {debt['person']}"
    else:
        tx['type'] = 'expense'
        tx['categoryId'] = 'Debt Repayment'
        tx['description'] = f"Repayment to {debt['person']}"

    current_app.db.transactions.insert_one(tx)

    new_remaining_amount = debt['remainingAmount'] - repayment_amount
    new_status = 'settled' if new_remaining_amount <= 0.001 else 'open'

    current_app.db.debts.update_one(
        {'_id': ObjectId(debt_id)},
        {
            '$inc': {'remainingAmount': -repayment_amount},
            '$push': {'repayments': {'amount': repayment_amount, 'date': datetime.utcnow()}},
            '$set': {'status': new_status}
        }
    )

    return jsonify({
        'message': 'Repayment recorded successfully',
        'remainingAmount': new_remaining_amount
    })