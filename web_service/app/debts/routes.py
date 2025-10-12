# --- Start of modified file: web_service/app/debts/routes.py ---
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from bson import ObjectId
import re
from zoneinfo import ZoneInfo

debts_bp = Blueprint('debts', __name__, url_prefix='/debts')
UTC_TZ = ZoneInfo("UTC")

def serialize_debt(doc):
    """Serializes a debt document from MongoDB for JSON responses."""
    if '_id' in doc:
        doc['_id'] = str(doc['_id'])
    if 'created_at' in doc and isinstance(doc['created_at'], datetime):
        doc['created_at'] = doc['created_at'].isoformat()
    return doc


@debts_bp.route('/', methods=['POST'])
def add_debt():
    """Adds a new debt and a corresponding transaction to reflect the balance change."""
    data = request.json
    if not all(k in data for k in ['type', 'person', 'amount', 'currency']):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        amount = float(data['amount'])
    except ValueError:
        return jsonify({'error': 'Amount must be a number'}), 400

    timestamp_str = data.get('timestamp')
    created_at = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(UTC_TZ)

    debt = {
        "type": data['type'], "person": data['person'].strip().title(),
        "originalAmount": amount, "remainingAmount": amount, "currency": data['currency'],
        "status": "open", "purpose": data.get("purpose", ""), "repayments": [],
        "created_at": created_at
    }

    account_name = f"{data['currency']} Account"
    tx_data = {
        "amount": amount, "currency": data['currency'], "accountName": account_name,
        "timestamp": created_at, "description": f"Loan {data['type']} {data['person']}"
    }

    if data['type'] == 'lent':
        tx_data['type'], tx_data['categoryId'] = 'expense', 'Loan Lent'
    else:
        tx_data['type'], tx_data['categoryId'] = 'income', 'Loan Received'

    current_app.db.transactions.insert_one(tx_data)
    result = current_app.db.debts.insert_one(debt)
    return jsonify({'message': 'Debt recorded', 'id': str(result.inserted_id)}), 201


@debts_bp.route('/', methods=['GET'])
def get_open_debts():
    """Fetches and groups open debts by person and currency, case-insensitively."""
    pipeline = [
        {'$match': {'status': 'open'}},
        {'$group': {
            '_id': {'person_normalized': {'$toLower': '$person'}, 'currency': '$currency', 'type': '$type'},
            'person_display': {'$first': '$person'},
            'totalAmount': {'$sum': '$remainingAmount'},
            'count': {'$sum': 1}
        }},
        {'$project': {
            '_id': 0, 'person': '$person_display', 'currency': '$_id.currency',
            'type': '$_id.type', 'totalAmount': '$totalAmount', 'count': '$count'
        }},
        {'$sort': {'person': 1}}
    ]
    grouped_debts = list(current_app.db.debts.aggregate(pipeline))
    return jsonify(grouped_debts)


@debts_bp.route('/<debt_id>', methods=['GET'])
def get_debt_details(debt_id):
    debt = current_app.db.debts.find_one({'_id': ObjectId(debt_id)})
    if not debt: return jsonify({'error': 'Debt not found'}), 404
    return jsonify(serialize_debt(debt))


@debts_bp.route('/person/<person_name>/<currency>', methods=['GET'])
def get_debts_by_person_and_currency(person_name, currency):
    query_filter = {
        'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
        'currency': currency, 'status': 'open'
    }
    debts = list(current_app.db.debts.find(query_filter).sort('created_at', 1))
    return jsonify([serialize_debt(d) for d in debts])


@debts_bp.route('/person/<person_name>/<currency>/repay', methods=['POST'])
def record_lump_sum_repayment(person_name, currency):
    """
    Handles a lump-sum repayment. If the repayment is an overpayment,
    it settles the debt and records the difference as interest income.
    """
    data = request.json
    if 'amount' not in data: return jsonify({'error': 'Repayment amount is required'}), 400

    try:
        repayment_amount = float(data['amount'])
        if repayment_amount <= 0: return jsonify({'error': 'Amount must be a positive number'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Amount must be a number'}), 400

    query_filter = {
        'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
        'currency': currency, 'status': 'open'
    }
    debts_to_repay = list(current_app.db.debts.find(query_filter).sort('created_at', 1))

    if not debts_to_repay:
        return jsonify({'error': 'No open debts found for this person and currency'}), 404

    total_remaining = sum(d['remainingAmount'] for d in debts_to_repay)
    debt_type = debts_to_repay[0]['type']
    now_utc = datetime.now(UTC_TZ)

    interest_amount = 0
    amount_to_apply_to_debt = repayment_amount

    # --- THIS IS THE NEW LOGIC ---
    if repayment_amount > total_remaining + 0.001: # It's an overpayment
        interest_amount = repayment_amount - total_remaining
        amount_to_apply_to_debt = total_remaining # Only apply the exact debt amount to the debts

        # Create a new income transaction for the interest
        interest_tx = {
            "type": "income", "amount": interest_amount, "currency": currency,
            "categoryId": "Loan Interest", "accountName": f"{currency} Account",
            "description": f"Interest from {person_name}", "timestamp": now_utc
        }
        current_app.db.transactions.insert_one(interest_tx)

    # Process the repayment for the debts (either the full or partial amount)
    amount_left_to_apply = amount_to_apply_to_debt
    for debt in debts_to_repay:
        if amount_left_to_apply <= 0: break
        repayment_for_this_debt = min(amount_left_to_apply, debt['remainingAmount'])
        new_remaining = debt['remainingAmount'] - repayment_for_this_debt
        new_status = 'settled' if new_remaining <= 0.001 else 'open'

        current_app.db.debts.update_one(
            {'_id': debt['_id']},
            {
                '$inc': {'remainingAmount': -repayment_for_this_debt},
                '$push': {'repayments': {'amount': repayment_for_this_debt, 'date': now_utc}},
                '$set': {'status': new_status}
            }
        )
        amount_left_to_apply -= repayment_for_this_debt

    # Create the main transaction for the debt repayment portion
    tx_category = 'Debt Settled' if debt_type == 'lent' else 'Debt Repayment'
    tx_type = 'income' if debt_type == 'lent' else 'expense'
    tx_desc = f"Repayment from {person_name}" if debt_type == 'lent' else f"Repayment to {person_name}"
    tx = {
        "type": tx_type, "amount": amount_to_apply_to_debt, "currency": currency,
        "categoryId": tx_category, "accountName": f"{currency} Account",
        "description": tx_desc, "timestamp": now_utc
    }
    current_app.db.transactions.insert_one(tx)

    # Craft the final success message
    final_message = f"✅ Repayment of {repayment_amount:,.2f} {currency} recorded for {person_name}."
    if interest_amount > 0:
        final_message += f"\nThe debt of {total_remaining:,.2f} {currency} is now settled. The extra {interest_amount:,.2f} {currency} was recorded as 'Loan Interest' income."

    return jsonify({'message': final_message})


@debts_bp.route('/analysis', methods=['GET'])
def get_debt_analysis():
    now = datetime.now(UTC_TZ)
    concentration_pipeline = [
        {'$match': {'status': 'open'}},
        {'$group': {
            '_id': {'person_normalized': {'$toLower': '$person'}, 'type': '$type'},
            'person_display': {'$first': '$person'}, 'totalAmount': {'$sum': '$remainingAmount'}
        }},
        {'$sort': {'totalAmount': -1}},
        {'$project': { '_id': 0, 'person': '$person_display', 'type': '$_id.type', 'total': '$totalAmount' }}
    ]
    aging_pipeline = [
        {'$match': {'status': 'open'}},
        {'$project': {
            'person': '$person',
            'age_in_days': {'$divide': [{'$subtract': [now, '$created_at']}, 1000 * 60 * 60 * 24]}
        }},
        {'$group': {
            '_id': {'$toLower': '$person'}, 'person_display': {'$first': '$person'},
            'averageAgeDays': {'$avg': '$age_in_days'}, 'count': {'$sum': 1}
        }},
        {'$project': { '_id': '$person_display', 'averageAgeDays': '$averageAgeDays', 'count': '$count' }},
        {'$sort': {'averageAgeDays': -1}}
    ]
    analysis = {
        'concentration': list(current_app.db.debts.aggregate(concentration_pipeline)),
        'aging': list(current_app.db.debts.aggregate(aging_pipeline))
    }
    return jsonify(analysis)