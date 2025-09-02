from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from bson import ObjectId
from urllib.parse import unquote

debts_bp = Blueprint('debts', __name__, url_prefix='/debts')


def serialize_debt(doc):
    """Recursively converts ObjectId and datetime objects to strings."""
    if isinstance(doc, list):
        return [serialize_debt(item) for item in doc]
    if isinstance(doc, dict):
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                doc[key] = str(value)
            elif isinstance(value, datetime):
                doc[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                serialize_debt(value)
    return doc


@debts_bp.route('/', methods=['POST'])
def add_debt():
    data = request.json
    if not all(k in data for k in ['type', 'person', 'amount', 'currency']):
        return jsonify({'error': 'Missing required fields'}), 400

    amount = float(data['amount'])
    debt = {
        "type": data['type'],
        "person": data['person'],
        "originalAmount": amount,
        "remainingAmount": amount,
        "currency": data['currency'],
        "purpose": data.get("purpose", ""),
        "status": "open",
        "repayments": [],
        "created_at": datetime.utcnow()
    }
    result = current_app.db.debts.insert_one(debt)

    account_name = "USD Account" if data['currency'] == "USD" else "KHR Account"
    tx = {
        "amount": amount,
        "currency": data['currency'],
        "accountName": account_name,
        "description": f"Loan related to {data['person']} for {data.get('purpose', 'N/A')}",
        "timestamp": datetime.utcnow()
    }

    if data['type'] == 'lent':
        tx['type'] = 'expense'
        tx['categoryId'] = 'Loan Lent'
    elif data['type'] == 'borrowed':
        tx['type'] = 'income'
        tx['categoryId'] = 'Loan Received'

    current_app.db.transactions.insert_one(tx)
    return jsonify({'message': 'Debt recorded', 'id': str(result.inserted_id)}), 201


@debts_bp.route('/', methods=['GET'])
def get_open_debts():
    """Returns a list of debts grouped by person and currency."""
    pipeline = [
        {'$match': {'status': 'open'}},
        {
            '$group': {
                '_id': {'person': '$person', 'currency': '$currency', 'type': '$type'},
                'totalAmount': {'$sum': '$remainingAmount'},
                'count': {'$sum': 1}
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


@debts_bp.route('/person/<person_name>/<currency>', methods=['GET'])
def get_debts_by_person_and_currency(person_name, currency):
    """Returns all individual open debts for a specific person and currency."""
    decoded_name = unquote(person_name)
    debts = list(current_app.db.debts.find({
        'person': decoded_name,
        'currency': currency,
        'status': 'open'
    }).sort('created_at', 1))
    return jsonify(serialize_debt(debts))


@debts_bp.route('/<debt_id>', methods=['GET'])
def get_debt_details(debt_id):
    debt = current_app.db.debts.find_one({'_id': ObjectId(debt_id)})
    if not debt:
        return jsonify({'error': 'Debt not found'}), 404
    return jsonify(serialize_debt(debt))


@debts_bp.route('/person/<person_name>/<currency>/repay', methods=['POST'])
def record_lump_sum_repayment(person_name, currency):
    """Applies a lump-sum repayment across the oldest debts first."""
    data = request.json
    if 'amount' not in data:
        return jsonify({'error': 'Amount is required'}), 400

    try:
        total_repayment = float(data['amount'])
    except ValueError:
        return jsonify({'error': 'Amount must be a number'}), 400

    decoded_name = unquote(person_name)
    debts_to_settle = list(current_app.db.debts.find({
        'person': decoded_name,
        'currency': currency,
        'status': 'open'
    }).sort('created_at', 1))

    if not debts_to_settle:
        return jsonify({'error': 'No open debts found for this person and currency'}), 404

    settled_count = 0
    partially_paid_count = 0
    account_name = "USD Account" if currency == "USD" else "KHR Account"

    for debt in debts_to_settle:
        if total_repayment <= 0:
            break

        remaining_on_this_debt = debt['remainingAmount']
        payment_for_this_debt = min(total_repayment, remaining_on_this_debt)

        # Create transaction for this portion of the repayment
        tx = {"amount": payment_for_this_debt, "currency": currency, "accountName": account_name, "timestamp": datetime.utcnow()}
        if debt['type'] == 'lent':
            tx['type'] = 'income'
            tx['categoryId'] = 'Debt Settled'
            tx['description'] = f"Repayment from {debt['person']}"
        else: # borrowed
            tx['type'] = 'expense'
            tx['categoryId'] = 'Debt Repayment'
            tx['description'] = f"Repayment to {debt['person']}"
        current_app.db.transactions.insert_one(tx)

        # Update debt document
        new_remaining = remaining_on_this_debt - payment_for_this_debt
        new_status = 'settled' if new_remaining <= 0.001 else 'open'

        current_app.db.debts.update_one(
            {'_id': debt['_id']},
            {
                '$set': {'remainingAmount': new_remaining, 'status': new_status},
                '$push': {'repayments': {'amount': payment_for_this_debt, 'date': datetime.utcnow()}}
            }
        )

        total_repayment -= payment_for_this_debt

        if new_status == 'settled':
            settled_count += 1
        else:
            partially_paid_count += 1

    message_parts = []
    if settled_count > 0:
        message_parts.append(f"settled {settled_count} loan{'s' if settled_count > 1 else ''}")
    if partially_paid_count > 0:
        message_parts.append(f"partially paid 1 loan")

    final_message = f"Repayment of {data['amount']} {currency} applied. Successfully {', and '.join(message_parts)}."
    return jsonify({'message': final_message})