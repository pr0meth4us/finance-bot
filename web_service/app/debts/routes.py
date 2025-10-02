# --- Start of modified file: web_service/app/debts/routes.py ---
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from bson import ObjectId
import re

debts_bp = Blueprint('debts', __name__, url_prefix='/debts')


def serialize_debt(doc):
    """
    Serializes a debt document from MongoDB for JSON responses.
    Converts ObjectId to string and datetime to ISO 8601 format string.
    """
    if '_id' in doc:
        doc['_id'] = str(doc['_id'])

    # Explicitly convert datetime to ISO 8601 format string to ensure frontend compatibility
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
    try:
        created_at = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.utcnow()
    except (ValueError, TypeError):
        created_at = datetime.utcnow()

    debt = {
        "type": data['type'],
        "person": data['person'].strip().title(),
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
    else:
        tx_data['type'] = 'income'
        tx_data['categoryId'] = 'Loan Received'

    current_app.db.transactions.insert_one(tx_data)
    result = current_app.db.debts.insert_one(debt)
    return jsonify({'message': 'Debt recorded', 'id': str(result.inserted_id)}), 201


@debts_bp.route('/', methods=['GET'])
def get_open_debts():
    """
    Fetches open debts and groups them by person and currency to provide a summary.
    This aggregation provides the `totalAmount` and `count` fields expected by the bot's keyboard.
    """
    pipeline = [
        {'$match': {'status': 'open'}},
        {
            '$group': {
                '_id': {
                    'person_normalized': {'$toLower': '$person'},
                    'currency': '$currency',
                    'type': '$type'
                },
                'person_display': {'$first': '$person'},
                'totalAmount': {'$sum': '$remainingAmount'},
                'count': {'$sum': 1}
            }
        },
        {
            '$project': {
                '_id': 0,
                'person': '$person_display',
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


@debts_bp.route('/<debt_id>', methods=['GET'])
def get_debt_details(debt_id):
    """Fetches the details of a single debt document by its ID."""
    debt = current_app.db.debts.find_one({'_id': ObjectId(debt_id)})
    if not debt:
        return jsonify({'error': 'Debt not found'}), 404
    return jsonify(serialize_debt(debt))


@debts_bp.route('/person/<person_name>/<currency>', methods=['GET'])
def get_debts_by_person_and_currency(person_name, currency):
    """Fetches all individual open debts for a specific person and currency."""
    query_filter = {
        'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
        'currency': currency,
        'status': 'open'
    }
    debts = list(current_app.db.debts.find(query_filter).sort('created_at', 1))
    return jsonify([serialize_debt(d) for d in debts])


@debts_bp.route('/person/<person_name>/<currency>/repay', methods=['POST'])
def record_lump_sum_repayment(person_name, currency):
    """Handles a lump-sum repayment, applying it to the oldest debts first."""
    data = request.json
    if 'amount' not in data:
        return jsonify({'error': 'Repayment amount is required'}), 400

    try:
        repayment_amount = float(data['amount'])
        if repayment_amount <= 0:
            return jsonify({'error': 'Amount must be a positive number'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Amount must be a number'}), 400

    query_filter = {
        'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
        'currency': currency,
        'status': 'open'
    }
    debts_to_repay = list(current_app.db.debts.find(query_filter).sort('created_at', 1))

    if not debts_to_repay:
        return jsonify({'error': 'No open debts found for this person and currency'}), 404

    total_remaining = sum(d['remainingAmount'] for d in debts_to_repay)
    if repayment_amount > total_remaining + 0.001:  # Allow for float inaccuracies
        return jsonify(
            {'error': f'Repayment amount {repayment_amount} is greater than total owed {total_remaining:.2f}'}), 400

    amount_to_apply = repayment_amount
    debt_type = debts_to_repay[0]['type']

    for debt in debts_to_repay:
        if amount_to_apply <= 0:
            break

        repayment_for_this_debt = min(amount_to_apply, debt['remainingAmount'])

        new_remaining = debt['remainingAmount'] - repayment_for_this_debt
        new_status = 'settled' if new_remaining <= 0.001 else 'open'

        current_app.db.debts.update_one(
            {'_id': debt['_id']},
            {
                '$inc': {'remainingAmount': -repayment_for_this_debt},
                '$push': {'repayments': {'amount': repayment_for_this_debt, 'date': datetime.utcnow()}},
                '$set': {'status': new_status}
            }
        )

        account_name = "USD Account" if currency == "USD" else "KHR Account"
        tx_category = 'Debt Settled' if debt_type == 'lent' else 'Debt Repayment'
        tx_type = 'income' if debt_type == 'lent' else 'expense'
        tx_desc = f"Repayment from {person_name}" if debt_type == 'lent' else f"Repayment to {person_name}"

        tx = {
            "type": tx_type, "amount": repayment_for_this_debt, "currency": currency,
            "categoryId": tx_category, "accountName": account_name,
            "description": tx_desc, "timestamp": datetime.utcnow()
        }
        current_app.db.transactions.insert_one(tx)

        amount_to_apply -= repayment_for_this_debt

    return jsonify(
        {'message': f'Successfully recorded repayment of {repayment_amount:,.2f} {currency} for {person_name}.'})


@debts_bp.route('/analysis', methods=['GET'])
def get_debt_analysis():
    """
    Analyzes open debts to find concentration by person and the average
    age of outstanding debts.
    """
    now = datetime.utcnow()

    # --- 1. Debt Concentration ---
    concentration_pipeline = [
        {'$match': {'status': 'open'}},
        {'$group': {
            '_id': {
                'person_normalized': {'$toLower': '$person'},
                'type': '$type'
            },
            'person_display': {'$first': '$person'},
            'totalAmount': {'$sum': '$remainingAmount'}
        }},
        {'$sort': {'totalAmount': -1}},
        {'$project': {
            '_id': 0,
            'person': '$person_display',
            'type': '$_id.type',
            'total': '$totalAmount'
        }}
    ]

    # --- 2. Debt Aging ---
    aging_pipeline = [
        {'$match': {'status': 'open'}},
        {'$project': {
            'person': '$person',
            'age_in_days': {
                '$divide': [{'$subtract': [now, '$created_at']}, 1000 * 60 * 60 * 24]
            }
        }},
        {'$group': {
            '_id': '$person',
            'averageAgeDays': {'$avg': '$age_in_days'},
            'count': {'$sum': 1}
        }},
        {'$sort': {'averageAgeDays': -1}}
    ]

    analysis = {
        'concentration': list(current_app.db.debts.aggregate(concentration_pipeline)),
        'aging': list(current_app.db.debts.aggregate(aging_pipeline))
    }

    return jsonify(analysis)