# --- web_service/app/debts/routes.py (Refactored) ---
"""
Handles all API endpoints related to IOU/Debt management.
All endpoints are multi-tenant and require a valid user_id.
"""
from flask import Blueprint, request, jsonify, g
from datetime import datetime
from bson import ObjectId
import re
from zoneinfo import ZoneInfo
from app.utils.currency import get_live_usd_to_khr_rate
from app.utils.db import get_db, settings_collection, debts_collection, transactions_collection
# --- REFACTOR: Import new auth decorator ---
from app.utils.auth import auth_required

debts_bp = Blueprint('debts', __name__, url_prefix='/debts')
UTC_TZ = ZoneInfo("UTC")


def serialize_debt(doc):
    """Serializes a debt document from MongoDB for JSON responses."""
    if '_id' in doc:
        doc['_id'] = str(doc['_id'])
    # --- REFACTOR: Use account_id ---
    if 'account_id' in doc:
        doc['account_id'] = str(doc['account_id'])
    if 'created_at' in doc and isinstance(doc['created_at'], datetime):
        doc['created_at'] = doc['created_at'].isoformat()
    if 'associated_transaction_id' in doc and isinstance(doc['associated_transaction_id'], ObjectId):
        doc['associated_transaction_id'] = str(doc['associated_transaction_id'])
    if 'repayments' in doc:
        for rep in doc['repayments']:
            if 'date' in rep and isinstance(rep['date'], datetime):
                rep['date'] = rep['date'].isoformat()
    return doc


def get_db_rate(db, account_id):
    """
    Helper to fetch the stored KHR rate from a user's settings.
    This is now user-specific.
    """
    # --- REFACTOR: Use 'db.settings' and query by 'account_id' ---
    settings_doc = settings_collection().find_one({'account_id': account_id})
    if settings_doc and 'settings' in settings_doc:
        settings = settings_doc['settings']
        if settings.get('rate_preference') == 'fixed':
             rate = float(settings.get('fixed_rate', 4100.0))
             if rate > 0:
                return rate
    return get_live_usd_to_khr_rate() # Default to live rate


@debts_bp.route('/', methods=['POST'])
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def add_debt():
    """Adds a new debt for the authenticated user."""
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    data = request.json
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
        "account_id": account_id, # <-- REFACTOR
        "amount": amount,
        "currency": data['currency'],
        "accountName": account_name,
        "timestamp": created_at,
        "description": f"Loan {data['type']} {data['person']}"
    }

    if data['type'] == 'lent':
        tx_data['type'], tx_data['categoryId'] = 'expense', 'Loan Lent'
    else:
        tx_data['type'], tx_data['categoryId'] = 'income', 'Loan Received'

    tx_result = transactions_collection().insert_one(tx_data)
    tx_id = tx_result.inserted_id

    debt = {
        "account_id": account_id, # <-- REFACTOR
        "type": data['type'],
        "person": data['person'].strip().title(),
        "originalAmount": amount,
        "remainingAmount": amount,
        "currency": data['currency'],
        "status": "open",
        "purpose": data.get("purpose", ""),
        "repayments": [],
        "created_at": created_at,
        "associated_transaction_id": tx_id
    }

    result = debts_collection().insert_one(debt)
    return jsonify({'message': 'Debt recorded', 'id': str(result.inserted_id)}), 201


@debts_bp.route('/', methods=['GET'])
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def get_open_debts():
    """Fetches and groups open debts for the authenticated user."""
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    pipeline = [
        {'$match': {'status': 'open', 'account_id': account_id}}, # <-- REFACTOR
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
    grouped_debts = list(debts_collection().aggregate(pipeline))
    return jsonify(grouped_debts)


@debts_bp.route('/export/open', methods=['GET'])
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def get_open_debts_export_list():
    """Fetches a simple flat list of all open debts for export."""
    db = get_db()
    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    query_filter = {
        'status': 'open',
        'account_id': account_id # <-- REFACTOR
    }
    debts = list(debts_collection().find(query_filter).sort('created_at', 1))
    return jsonify([serialize_debt(d) for d in debts])


@debts_bp.route('/list/settled', methods=['GET'])
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def get_settled_debts_grouped():
    """Fetches and groups settled OR canceled debts for the authenticated user."""
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    pipeline = [
        {'$match': {
            'status': {'$in': ['settled', 'canceled']},
            'account_id': account_id  # <-- REFACTOR
        }},
        {'$group': {
            '_id': {'person_normalized': {'$toLower': '$person'}, 'currency': '$currency', 'type': '$type'},
            'person_display': {'$first': '$person'},
            'totalAmount': {'$sum': '$originalAmount'},
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
    grouped_debts = list(debts_collection().aggregate(pipeline))
    return jsonify(grouped_debts)


@debts_bp.route('/<debt_id>', methods=['GET'])
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def get_debt_details(debt_id):
    """Fetches details for a single debt owned by the authenticated user."""
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    debt = debts_collection().find_one({
        '_id': ObjectId(debt_id),
        'account_id': account_id # <-- REFACTOR
    })

    if not debt:
        return jsonify({'error': 'Debt not found or access denied'}), 404
    return jsonify(serialize_debt(debt))


@debts_bp.route('/person/<person_name>/<currency>', methods=['GET'])
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def get_debts_by_person_and_currency(person_name, currency):
    """Fetches debts by person/currency for the authenticated user."""
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    query_filter = {
        'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
        'currency': currency,
        'status': 'open',
        'account_id': account_id # <-- REFACTOR
    }
    debts = list(debts_collection().find(query_filter).sort('created_at', 1))
    return jsonify([serialize_debt(d) for d in debts])


@debts_bp.route('/person/<person_name>/all', methods=['GET'])
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def get_all_debts_by_person(person_name):
    """Fetches all open debts for a person, for the authenticated user."""
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    query_filter = {
        'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
        'status': 'open',
        'account_id': account_id # <-- REFACTOR
    }
    debts = list(debts_collection().find(query_filter).sort('created_at', 1))
    return jsonify([serialize_debt(d) for d in debts])


@debts_bp.route('/person/<person_name>/all/settled', methods=['GET'])
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def get_all_settled_debts_by_person(person_name):
    """Fetches all settled debts for a person, for the authenticated user."""
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    query_filter = {
        'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
        'status': {'$in': ['settled', 'canceled']},
        'account_id': account_id # <-- REFACTOR
    }
    debts = list(debts_collection().find(query_filter).sort('created_at', 1))
    return jsonify([serialize_debt(d) for d in debts])


@debts_bp.route('/person/<payment_currency>/repay', methods=['POST'])
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def record_lump_sum_repayment(payment_currency):
    """Handles a lump-sum repayment for the authenticated user."""
    data = request.json
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    if 'amount' not in data or 'type' not in data or 'person' not in data:
        return jsonify({'error': 'Repayment amount, type, and person are required'}), 400

    debt_type = data['type']
    person_name = data['person']

    if debt_type not in ['lent', 'borrowed']:
        return jsonify({'error': "Invalid debt type, must be 'lent' or 'borrowed'"}), 400

    try:
        payment_amount = float(data['amount'])
        if payment_amount <= 0: return jsonify({'error': 'Amount must be a positive number'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Amount must be a number'}), 400

    timestamp_str = data.get('timestamp')
    payment_time_utc = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(UTC_TZ)

    # --- CROSS-CURRENCY LOGIC (Now user-specific) ---
    query_filter = {
        'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
        'currency': payment_currency,
        'status': 'open',
        'type': debt_type,
        'account_id': account_id # <-- REFACTOR
    }
    debts_to_process = list(debts_collection().find(query_filter).sort('created_at', 1))

    debt_currency = payment_currency
    converted_payment_amount = payment_amount

    if not debts_to_process:
        alternate_currency = 'USD' if payment_currency == 'KHR' else 'KHR'
        query_filter['currency'] = alternate_currency
        alternate_debts = list(debts_collection().find(query_filter).sort('created_at', 1))

        if not alternate_debts:
            return jsonify({'error': f'No open {debt_type} debts found for {person_name} in any currency'}), 404

        debts_to_process = alternate_debts
        debt_currency = alternate_currency

        # --- REFACTOR: Use user-specific rate ---
        rate = get_db_rate(db, account_id)

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
            interest_tx_type, interest_category = "income", "Loan Interest"
            interest_desc = f"Interest from {person_name}"
        else:
            interest_tx_type, interest_category = "expense", "Interest Expense"
            interest_desc = f"Interest paid to {person_name}"

        interest_tx = {
            "account_id": account_id, # <-- REFACTOR
            "type": interest_tx_type,
            "amount": interest_amount,
            "currency": debt_currency,
            "categoryId": interest_category,
            "accountName": f"{debt_currency} Account",
            "description": interest_desc,
            "timestamp": payment_time_utc
        }
        transactions_collection().insert_one(interest_tx)

    amount_left_to_apply = amount_to_apply_to_principal
    for debt in debts_to_process:
        if amount_left_to_apply <= 0: break
        repayment_for_this_debt = min(amount_left_to_apply, debt['remainingAmount'])
        new_remaining = debt['remainingAmount'] - repayment_for_this_debt
        new_status = 'settled' if new_remaining <= 0.001 else 'open'

        debts_collection().update_one(
            {'_id': debt['_id'], 'account_id': account_id}, # <-- REFACTOR
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
        "account_id": account_id, # <-- REFACTOR
        "type": tx_type,
        "amount": payment_amount,
        "currency": payment_currency,
        "categoryId": tx_category,
        "accountName": f"{payment_currency} Account",
        "description": tx_desc,
        "timestamp": payment_time_utc
    }
    transactions_collection().insert_one(tx)

    payment_format = ",.0f" if payment_currency == 'KHR' else ",.2f"
    debt_format = ",.0f" if debt_currency == 'KHR' else ",.2f"
    final_message = f"✅ Repayment of {payment_amount:{payment_format}} {payment_currency} recorded for {person_name}."

    if debt_currency != payment_currency:
        final_message += f"\n(Converted to {converted_payment_amount:{debt_format}} {debt_currency} and applied to debt)."
    if interest_amount > 0:
        if debt_type == 'lent':
            final_message += f"\nThe debt of {total_remaining_debt:{debt_format}} {debt_currency} is now settled.\nThe extra {interest_amount:{debt_format}} {debt_currency} was recorded as 'Loan Interest' income."
        else:
            final_message += f"\nThe debt of {total_remaining_debt:{debt_format}} {debt_currency} is now settled.\nThe extra {interest_amount:{debt_format}} {debt_currency} was recorded as 'Interest Expense'."

    return jsonify({'message': final_message})


@debts_bp.route('/<debt_id>/cancel', methods=['POST'])
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def cancel_debt(debt_id):
    """Cancels a debt and reverses the initial transaction for the authenticated user."""
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    try:
        debt = debts_collection().find_one({
            '_id': ObjectId(debt_id),
            'account_id': account_id # <-- REFACTOR
        })
        if not debt:
            return jsonify({'error': 'Debt not found or access denied'}), 404

        if debt['status'] == 'canceled':
            return jsonify({'error': 'Debt is already canceled'}), 400

        tx_id = debt.get('associated_transaction_id')
        if not tx_id:
            return jsonify({'error': 'Cannot cancel debt: No associated transaction found.'}), 500

        original_tx = transactions_collection().find_one({
            '_id': ObjectId(tx_id),
            'account_id': account_id # <-- REFACTOR
        })
        if not original_tx:
            return jsonify({'error': 'Cannot cancel debt: Original transaction not found.'}), 500

        reverse_type = 'income' if original_tx['type'] == 'expense' else 'expense'
        reverse_desc = f"Reversal for Canceled Debt: {original_tx['description']}"

        reverse_tx = {
            "account_id": account_id, # <-- REFACTOR
            "type": reverse_type,
            "amount": original_tx['amount'],
            "currency": original_tx['currency'],
            "categoryId": "Canceled Debt",
            "accountName": original_tx['accountName'],
            "description": reverse_desc,
            "timestamp": datetime.now(UTC_TZ)
        }
        transactions_collection().insert_one(reverse_tx)

        debts_collection().update_one(
            {'_id': ObjectId(debt_id), 'account_id': account_id}, # <-- REFACTOR
            {'$set': {'status': 'canceled', 'remainingAmount': 0}}
        )

        return jsonify({'message': 'Debt canceled and transaction reversed.'})
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


@debts_bp.route('/<debt_id>', methods=['PUT'])
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def update_debt(debt_id):
    """Updates the person or purpose of a debt for the authenticated user."""
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    data = request.json
    if not data or not any(k in data for k in ['person', 'purpose']):
        return jsonify({'error': 'No valid fields (person, purpose) provided for update.'}), 400

    update_fields = {}
    if 'person' in data:
        update_fields['person'] = data['person'].strip().title()
    if 'purpose' in data:
        update_fields['purpose'] = data['purpose'].strip()

    result = debts_collection().update_one(
        {'_id': ObjectId(debt_id), 'account_id': account_id}, # <-- REFACTOR
        {'$set': update_fields}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'Debt not found or access denied'}), 404

    return jsonify({'message': 'Debt updated successfully'})


@debts_bp.route('/analysis', methods=['GET'])
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def get_debt_analysis():
    """Generates a debt analysis for the authenticated user."""
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    now = datetime.now(UTC_TZ)

    # Base match stage for all pipelines
    # --- REFACTOR: Use account_id ---
    base_match = {'status': 'open', 'account_id': account_id}

    # --- Pipeline 1: Concentration (Top people) ---
    concentration_pipeline = [
        {'$match': base_match},
        {'$group': {
            '_id': {'person_normalized': {'$toLower': '$person'}, 'type': '$type'},
            'person_display': {'$first': '$person'},
            'totalAmount': {'$sum': '$remainingAmount'}
        }},
        {'$sort': {'totalAmount': -1}},
        {'$project': {'_id': 0, 'person': '$person_display', 'type': '$_id.type', 'total': '$totalAmount'}}
    ]

    # --- Pipeline 2: Aging (Oldest debts) ---
    aging_pipeline = [
        {'$match': base_match},
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

    # --- Pipeline 3: Overview (Total Owed vs. Total Lent in USD) ---
    # --- REFACTOR: Use user-specific rate ---
    rate = get_db_rate(db, account_id)
    overview_pipeline = [
        {'$match': base_match},
        {'$addFields': {
            'amount_in_usd': {
                '$cond': {
                    'if': {'$eq': ['$currency', 'USD']},
                    'then': '$remainingAmount',
                    'else': {'$divide': ['$remainingAmount', rate]}
                }
            }
        }},
        {'$group': {
            '_id': '$type',
            'total_usd': {'$sum': '$amount_in_usd'}
        }}
    ]

    # --- Execute Pipelines ---
    concentration_data = list(debts_collection().aggregate(concentration_pipeline))
    aging_data = list(debts_collection().aggregate(aging_pipeline))
    overview_data = list(debts_collection().aggregate(overview_pipeline))

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