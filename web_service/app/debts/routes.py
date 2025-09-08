# --- Start of modified file: web_service/app/debts/routes.py ---

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

    debt = {
        "type": data['type'],
        "person": data['person'],
        "originalAmount": amount,
        "remainingAmount": amount,
        "currency": data['currency'],
        "status": "open",
        "repayments": [],
        "created_at": datetime.utcnow()
    }

    # --- MODIFICATION START: Create corresponding transaction for balance calculation ---
    # When a loan is created, we create a transaction to update the main account balance.
    account_name = "USD Account" if data['currency'] == "USD" else "KHR Account"
    tx_data = {
        "amount": amount,
        "currency": data['currency'],
        "accountName": account_name,
        "timestamp": datetime.utcnow(),
        "description": f"Loan {data['type']} {data['person']}" # Description for clarity
    }

    if data['type'] == 'lent':
        tx_data['type'] = 'expense'
        tx_data['categoryId'] = 'Loan Lent' # Categorize as non-operational expense
    else: # type == 'borrowed'
        tx_data['type'] = 'income'
        tx_data['categoryId'] = 'Loan Received' # Categorize as non-operational income

    current_app.db.transactions.insert_one(tx_data)
    # --- MODIFICATION END ---

    result = current_app.db.debts.insert_one(debt)
    return jsonify({'message': 'Debt recorded', 'id': str(result.inserted_id)}), 201


@debts_bp.route('/', methods=['GET'])
def get_open_debts():
    debts = list(current_app.db.debts.find({'status': 'open'}))
    return jsonify([serialize_debt(d) for d in debts])


@debts_bp.route('/<debt_id>', methods=['GET'])
def get_debt_details(debt_id):
    debt = current_app.db.debts.find_one({'_id': ObjectId(debt_id)})
    if not debt:
        return jsonify({'error': 'Debt not found'}), 404
    return jsonify(serialize_debt(debt))


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

    # Check for over-repayment. Allow for small floating point inaccuracies.
    if repayment_amount > debt['remainingAmount'] + 0.001:
        return jsonify({'error': f"Repayment ({repayment_amount}) cannot be greater than the remaining amount ({debt['remainingAmount']})"}), 400

    # Create transaction for repayment
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
# --- End of modified file: web_service/app/debts/routes.py ---