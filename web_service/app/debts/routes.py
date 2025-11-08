# --- Start of modified file: web_service/app/debts/routes.py ---
from flask import Blueprint, request, jsonify
from datetime import datetime
from bson import ObjectId
import re
from zoneinfo import ZoneInfo
from app.utils.currency import get_live_usd_to_khr_rate
from app import get_db  # <-- IMPORT THE NEW FUNCTION

debts_bp = Blueprint('debts', __name__, url_prefix='/debts')
UTC_TZ = ZoneInfo("UTC")


def serialize_debt(doc):
    """Serializes a debt document from MongoDB for JSON responses."""
    if '_id' in doc:
        doc['_id'] = str(doc['_id'])
    if 'created_at' in doc and isinstance(doc['created_at'], datetime):
        doc['created_at'] = doc['created_at'].isoformat()

    if 'associated_transaction_id' in doc and isinstance(doc['associated_transaction_id'], ObjectId):
        doc['associated_transaction_id'] = str(doc['associated_transaction_id'])

    if 'repayments' in doc:
        for rep in doc['repayments']:
            if 'date' in rep and isinstance(rep['date'], datetime):
                rep['date'] = rep['date'].isoformat()
    return doc


def get_db_rate(db):
    """Helper to fetch the stored KHR rate from settings."""
    settings = db.settings.find_one({'_id': 'config'})
    if settings and 'khr_to_usd_rate' in settings:
        rate = float(settings['khr_to_usd_rate'])
        if rate > 0:
            return rate
    return 4100.0  # Default fallback


@debts_bp.route('/', methods=['POST'])
def add_debt():
    """Adds a new debt and a corresponding transaction to reflect the balance change."""
    data = request.json
    db = get_db()  # <-- USE THE NEW FUNCTION
    if not all(k in data for k in ['type', 'person', 'amount', 'currency']):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        amount = float(data['amount'])
    except ValueError:
        return jsonify({'error': 'Amount must be a number'}), 400

    timestamp_str = data.get('timestamp')
    created_at = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(UTC_TZ)
    account_name = f"{data['currency']} Account"

    tx_data = {
        "amount": amount, "currency": data['currency'], "accountName": account_name,
        "timestamp": created_at, "description": f"Loan {data['type']} {data['person']}"
    }

    if data['type'] == 'lent':
        tx_data['type'], tx_data['categoryId'] = 'expense', 'Loan Lent'
    else:
        tx_data['type'], tx_data['categoryId'] = 'income', 'Loan Received'

    tx_result = db.transactions.insert_one(tx_data)
    tx_id = tx_result.inserted_id

    debt = {
        "type": data['type'], "person": data['person'].strip().title(),
        "originalAmount": amount, "remainingAmount": amount, "currency": data['currency'],
        "status": "open", "purpose": data.get("purpose", ""), "repayments": [],
        "created_at": created_at,
        "associated_transaction_id": tx_id
    }

    result = db.debts.insert_one(debt)
    return jsonify({'message': 'Debt recorded', 'id': str(result.inserted_id)}), 201


@debts_bp.route('/', methods=['GET'])
def get_open_debts():
    """Fetches and groups open debts by person, consolidating currencies."""
    db = get_db()  # <-- USE THE NEW FUNCTION
    pipeline = [
        {'$match': {'status': 'open'}},
        {'$group': {
            '_id': {'person_normalized': {'$toLower': '$person'}, 'currency': '$currency', 'type': '$type'},
            'person_display': {'$first': '$person'},
            'totalAmount': {'$sum': '$remainingAmount'},
            'count': {'$sum': 1}
        }},
        {'$group': {
            '_id': {'person_normalized': '$_id.person_normalized', 'type': '$_id.type'},
            'person_display': {'$first': '$person_display'},
            'totals': {'$push': {'currency': '$_id.currency', 'total': '$totalAmount', 'count': '$count'}}
        }},
        {'$project': {
            '_id': 0,
            'person': '$person_display',
            'type': '$_id.type',
            'totals': '$totals'
        }},
        {'$sort': {'person': 1}}
    ]
    grouped_debts = list(db.debts.aggregate(pipeline))
    return jsonify(grouped_debts)


@debts_bp.route('/list/settled', methods=['GET'])
def get_settled_debts_grouped():
    """Fetches and groups settled OR canceled debts by person, consolidating currencies."""
    db = get_db()  # <-- USE THE NEW FUNCTION
    pipeline = [
        {'$match': {'status': {'$in': ['settled', 'canceled']}}},
        {'$group': {
            '_id': {'person_normalized': {'$toLower': '$person'}, 'currency': '$currency', 'type': '$type'},
            'person_display': {'$first': '$person'},
            'totalAmount': {'$sum': '$originalAmount'},  # Show original amount for settled
            'count': {'$sum': 1}
        }},
        {'$group': {
            '_id': {'person_normalized': '$_id.person_normalized', 'type': '$_id.type'},
            'person_display': {'$first': '$person_display'},
            'totals': {'$push': {'currency': '$_id.currency', 'total': '$totalAmount', 'count': '$count'}}
        }},
        {'$project': {
            '_id': 0,
            'person': '$person_display',
            'type': '$_id.type',
            'totals': '$totals'
        }},
        {'$sort': {'person': 1}}
    ]
    grouped_debts = list(db.debts.aggregate(pipeline))
    return jsonify(grouped_debts)


@debts_bp.route('/<debt_id>', methods=['GET'])
def get_debt_details(debt_id):
    db = get_db()  # <-- USE THE NEW FUNCTION
    debt = db.debts.find_one({'_id': ObjectId(debt_id)})
    if not debt: return jsonify({'error': 'Debt not found'}), 404
    return jsonify(serialize_debt(debt))


@debts_bp.route('/person/<person_name>/<currency>', methods=['GET'])
def get_debts_by_person_and_currency(person_name, currency):
    db = get_db()  # <-- USE THE NEW FUNCTION
    query_filter = {
        'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
        'currency': currency, 'status': 'open'
    }
    debts = list(db.debts.find(query_filter).sort('created_at', 1))
    return jsonify([serialize_debt(d) for d in debts])


@debts_bp.route('/person/<person_name>/all', methods=['GET'])
def get_all_debts_by_person(person_name):
    db = get_db()  # <-- USE THE NEW FUNCTION
    query_filter = {
        'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
        'status': 'open'
    }
    debts = list(db.debts.find(query_filter).sort('created_at', 1))
    return jsonify([serialize_debt(d) for d in debts])


@debts_bp.route('/person/<person_name>/all/settled', methods=['GET'])
def get_all_settled_debts_by_person(person_name):
    db = get_db()  # <-- USE THE NEW FUNCTION
    query_filter = {
        'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
        'status': {'$in': ['settled', 'canceled']}
    }
    debts = list(db.debts.find(query_filter).sort('created_at', 1))
    return jsonify([serialize_debt(d) for d in debts])


@debts_bp.route('/person/<payment_currency>/repay', methods=['POST'])
def record_lump_sum_repayment(payment_currency):
    """
    Handles a lump-sum repayment, including cross-currency logic.
    """
    data = request.json
    db = get_db()  # <-- USE THE NEW FUNCTION
    if 'amount' not in data or 'type' not in data:
        return jsonify({'error': 'Repayment amount and type are required'}), 400

    debt_type = data['type']  # 'lent' (someone pays me) or 'borrowed' (I pay someone)
    person_name = data['person']  # Person is now in the payload

    if debt_type not in ['lent', 'borrowed']:
        return jsonify({'error': "Invalid debt type, must be 'lent' or 'borrowed'"}), 400

    try:
        payment_amount = float(data['amount'])  # Amount in payment_currency
        if payment_amount <= 0: return jsonify({'error': 'Amount must be a positive number'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Amount must be a number'}), 400

    timestamp_str = data.get('timestamp')
    payment_time_utc = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(UTC_TZ)

    # --- CROSS-CURRENCY LOGIC ---

    query_filter = {
        'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
        'currency': payment_currency,
        'status': 'open',
        'type': debt_type
    }
    debts_to_process = list(db.debts.find(query_filter).sort('created_at', 1))

    debt_currency = payment_currency
    converted_payment_amount = payment_amount

    if not debts_to_process:
        alternate_currency = 'USD' if payment_currency == 'KHR' else 'KHR'
        query_filter['currency'] = alternate_currency
        alternate_debts = list(db.debts.find(query_filter).sort('created_at', 1))

        if not alternate_debts:
            return jsonify({'error': f'No open {debt_type} debts found for {person_name} in any currency'}), 404

        debts_to_process = alternate_debts
        debt_currency = alternate_currency

        # --- FIX: Call live rate function, not DB rate ---
        rate = get_live_usd_to_khr_rate()
        # --- End Fix ---

        if payment_currency == 'KHR' and debt_currency == 'USD':
            converted_payment_amount = payment_amount / rate
        elif payment_currency == 'USD' and debt_currency == 'KHR':
            converted_payment_amount = payment_amount * rate
        else:
            return jsonify({'error': 'Currency conversion error'}), 500

    # --- REPAYMENT AND INTEREST LOGIC ---

    total_remaining_debt = sum(d['remainingAmount'] for d in debts_to_process)

    interest_amount = 0
    amount_to_apply_to_principal = converted_payment_amount

    if converted_payment_amount > total_remaining_debt + 0.001:
        interest_amount = converted_payment_amount - total_remaining_debt
        amount_to_apply_to_principal = total_remaining_debt

        if debt_type == 'lent':
            interest_tx_type = "income"
            interest_category = "Loan Interest"
            interest_desc = f"Interest from {person_name}"
        else:
            interest_tx_type = "expense"
            interest_category = "Interest Expense"
            interest_desc = f"Interest paid to {person_name}"

        interest_tx = {
            "type": interest_tx_type,
            "amount": interest_amount,
            "currency": debt_currency,
            "categoryId": interest_category,
            "accountName": f"{debt_currency} Account",
            "description": interest_desc,
            "timestamp": payment_time_utc
        }
        db.transactions.insert_one(interest_tx)

    amount_left_to_apply = amount_to_apply_to_principal
    for debt in debts_to_process:
        if amount_left_to_apply <= 0: break
        repayment_for_this_debt = min(amount_left_to_apply, debt['remainingAmount'])
        new_remaining = debt['remainingAmount'] - repayment_for_this_debt
        new_status = 'settled' if new_remaining <= 0.001 else 'open'

        db.debts.update_one(
            {'_id': debt['_id']},
            {
                '$inc': {'remainingAmount': -repayment_for_this_debt},
                '$push': {'repayments': {'amount': repayment_for_this_debt, 'date': payment_time_utc}},
                '$set': {'status': new_status}
            }
        )
        amount_left_to_apply -= repayment_for_this_debt

    tx_category = 'Debt Settled' if debt_type == 'lent' else 'Debt Repayment'
    tx_type = 'income' if debt_type == 'lent' else 'expense'
    tx_desc = f"Repayment from {person_name}" if debt_type == 'lent' else f"Repayment to {person_name}"

    tx = {
        "type": tx_type,
        "amount": payment_amount,
        "currency": payment_currency,
        "categoryId": tx_category,
        "accountName": f"{payment_currency} Account",
        "description": tx_desc,
        "timestamp": payment_time_utc
    }
    db.transactions.insert_one(tx)

    payment_format = ",.0f" if payment_currency == 'KHR' else ",.2f"
    debt_format = ",.0f" if debt_currency == 'KHR' else ",.2f"

    final_message = f"✅ Repayment of {payment_amount:{payment_format}} {payment_currency} recorded for {person_name}."

    if debt_currency != payment_currency:
        final_message += f"\n(Converted to {converted_payment_amount:{debt_format}} {debt_currency} and applied to debt)."

    if interest_amount > 0:
        if debt_type == 'lent':
            final_message += f"\nThe debt of {total_remaining_debt:{debt_format}} {debt_currency} is now settled. The extra {interest_amount:{debt_format}} {debt_currency} was recorded as 'Loan Interest' income."
        else:
            final_message += f"\nThe debt of {total_remaining_debt:{debt_format}} {debt_currency} is now settled. The extra {interest_amount:{debt_format}} {debt_currency} was recorded as 'Interest Expense'."

    return jsonify({'message': final_message})


@debts_bp.route('/<debt_id>/cancel', methods=['POST'])
def cancel_debt(debt_id):
    db = get_db()  # <-- USE THE NEW FUNCTION
    try:
        debt = db.debts.find_one({'_id': ObjectId(debt_id)})
        if not debt:
            return jsonify({'error': 'Debt not found'}), 404

        if debt['status'] == 'canceled':
            return jsonify({'error': 'Debt is already canceled'}), 400

        tx_id = debt.get('associated_transaction_id')
        if not tx_id:
            return jsonify({'error': 'Cannot cancel debt: No associated transaction found.'}), 500

        original_tx = db.transactions.find_one({'_id': ObjectId(tx_id)})
        if not original_tx:
            return jsonify({'error': 'Cannot cancel debt: Original transaction not found.'}), 500

        if original_tx['type'] == 'expense':
            reverse_type = 'income'
            reverse_desc = f"Reversal for Canceled Debt: {original_tx['description']}"
        else:
            reverse_type = 'expense'
            reverse_desc = f"Reversal for Canceled Debt: {original_tx['description']}"

        reverse_tx = {
            "type": reverse_type,
            "amount": original_tx['amount'],
            "currency": original_tx['currency'],
            "categoryId": "Canceled Debt",
            "accountName": original_tx['accountName'],
            "description": reverse_desc,
            "timestamp": datetime.now(UTC_TZ)
        }
        db.transactions.insert_one(reverse_tx)

        db.debts.update_one(
            {'_id': ObjectId(debt_id)},
            {'$set': {'status': 'canceled', 'remainingAmount': 0}}
        )

        return jsonify({'message': 'Debt canceled and transaction reversed.'})

    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


@debts_bp.route('/<debt_id>', methods=['PUT'])
def update_debt(debt_id):
    db = get_db()  # <-- USE THE NEW FUNCTION
    data = request.json
    if not data or not any(k in data for k in ['person', 'purpose']):
        return jsonify({'error': 'No valid fields (person, purpose) provided for update.'}), 400

    update_fields = {}
    if 'person' in data:
        update_fields['person'] = data['person'].strip().title()
    if 'purpose' in data:
        update_fields['purpose'] = data['purpose'].strip()

    result = db.debts.update_one(
        {'_id': ObjectId(debt_id)},
        {'$set': update_fields}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'Debt not found'}), 404

    return jsonify({'message': 'Debt updated successfully'})


@debts_bp.route('/analysis', methods=['GET'])
def get_debt_analysis():
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    db = get_db()  # <-- USE THE NEW FUNCTION
    now = datetime.now(UTC_TZ)

    # --- Pipeline 1: Concentration (Top people) ---
    concentration_pipeline = [
        {'$match': {'status': 'open'}},
        {'$group': {
            '_id': {'person_normalized': {'$toLower': '$person'}, 'type': '$type'},
            'person_display': {'$first': '$person'},
            'totalAmount': {'$sum': '$remainingAmount'}  # Uses remainingAmount
        }},
        {'$sort': {'totalAmount': -1}},
        {'$project': {'_id': 0, 'person': '$person_display', 'type': '$_id.type', 'total': '$totalAmount'}}
    ]

    # --- Pipeline 2: Aging (Oldest debts) ---
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
        {'$project': {'_id': '$person_display', 'averageAgeDays': '$averageAgeDays', 'count': '$count'}},
        {'$sort': {'averageAgeDays': -1}}
    ]

    # --- NEW Pipeline 3: Overview (Total Owed vs. Total Lent in USD) ---
    rate = get_live_usd_to_khr_rate()
    overview_pipeline = [
        {'$match': {'status': 'open'}},
        {
            '$addFields': {
                'amount_in_usd': {
                    '$cond': {
                        'if': {'$eq': ['$currency', 'USD']},
                        'then': '$remainingAmount',
                        'else': {'$divide': ['$remainingAmount', rate]}
                    }
                }
            }
        },
        {
            '$group': {
                '_id': '$type',
                'total_usd': {'$sum': '$amount_in_usd'}
            }
        }
    ]

    # --- Execute Pipelines ---
    concentration_data = list(db.debts.aggregate(concentration_pipeline))
    aging_data = list(db.debts.aggregate(aging_pipeline))
    overview_data = list(db.debts.aggregate(overview_pipeline))

    # --- Format Response ---
    total_lent_usd = next((item['total_usd'] for item in overview_data if item['_id'] == 'lent'), 0)
    total_borrowed_usd = next((item['total_usd'] for item in overview_data if item['_id'] == 'borrowed'), 0)

    analysis = {
        'concentration': concentration_data,
        'aging': aging_data,
        'overview_usd': {
            'total_lent_usd': total_lent_usd,
            'total_borrowed_usd': total_borrowed_usd
        }
    }
    return jsonify(analysis)