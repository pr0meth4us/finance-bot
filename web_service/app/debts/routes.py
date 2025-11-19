from flask import Blueprint, request, jsonify, g
from datetime import datetime
from bson import ObjectId
import re
from zoneinfo import ZoneInfo
from pymongo import UpdateOne

from app.utils.db import get_db, settings_collection, debts_collection, transactions_collection
from app.utils.currency import get_live_usd_to_khr_rate
from app.utils.auth import auth_required

debts_bp = Blueprint('debts', __name__, url_prefix='/debts')
UTC_TZ = ZoneInfo("UTC")


def get_account_id():
    try:
        return ObjectId(g.account_id)
    except Exception:
        raise ValueError("Invalid account_id format")


def serialize_debt(doc):
    """Serializes a debt document for JSON."""
    if not doc:
        return None
    if '_id' in doc:
        doc['_id'] = str(doc['_id'])
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


def get_user_khr_rate(account_id):
    """Fetches the user's preferred KHR rate (fixed or live)."""
    doc = settings_collection().find_one(
        {'account_id': account_id},
        {'settings.rate_preference': 1, 'settings.fixed_rate': 1}
    )
    if doc and 'settings' in doc:
        settings = doc['settings']
        if settings.get('rate_preference') == 'fixed':
            rate = float(settings.get('fixed_rate', 4100.0))
            if rate > 0:
                return rate
    return get_live_usd_to_khr_rate()


@debts_bp.route('/', methods=['POST'])
@auth_required(min_role="premium_user")
def add_debt():
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id'}), 400

    data = request.json
    required = ['type', 'person', 'amount', 'currency']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing fields'}), 400

    try:
        amount = float(data['amount'])
        created_at = datetime.now(UTC_TZ)
        if data.get('timestamp'):
            created_at = datetime.fromisoformat(data['timestamp'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid data format'}), 400

    # Create associated transaction
    tx_data = {
        "account_id": account_id,
        "amount": amount,
        "currency": data['currency'],
        "accountName": f"{data['currency']} Account",
        "timestamp": created_at,
        "description": f"Loan {data['type']} {data['person']}"
    }

    if data['type'] == 'lent':
        tx_data.update({'type': 'expense', 'categoryId': 'Loan Lent'})
    else:
        tx_data.update({'type': 'income', 'categoryId': 'Loan Received'})

    tx_id = transactions_collection().insert_one(tx_data).inserted_id

    # Create debt record
    debt = {
        "account_id": account_id,
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

    debt_id = debts_collection().insert_one(debt).inserted_id
    return jsonify({'message': 'Debt recorded', 'id': str(debt_id)}), 201


@debts_bp.route('/', methods=['GET'])
@auth_required(min_role="premium_user")
def get_open_debts():
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id'}), 400

    pipeline = [
        {'$match': {'status': 'open', 'account_id': account_id}},
        {'$group': {
            '_id': {'person': {'$toLower': '$person'}, 'currency': '$currency', 'type': '$type'},
            'person_display': {'$first': '$person'},
            'totalAmount': {'$sum': '$remainingAmount'},
            'count': {'$sum': 1}
        }},
        {'$group': {
            '_id': {'person': '$_id.person', 'type': '$_id.type'},
            'person': {'$first': '$person_display'},
            'totals': {'$push': {'currency': '$_id.currency', 'total': '$totalAmount', 'count': '$count'}}
        }},
        {'$project': {'_id': 0, 'person': 1, 'type': '$_id.type', 'totals': 1}},
        {'$sort': {'person': 1}}
    ]
    return jsonify(list(debts_collection().aggregate(pipeline)))


@debts_bp.route('/export/open', methods=['GET'])
@auth_required(min_role="premium_user")
def get_open_debts_export_list():
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id'}), 400

    debts = list(debts_collection().find(
        {'status': 'open', 'account_id': account_id}
    ).sort('created_at', 1))

    return jsonify([serialize_debt(d) for d in debts])


@debts_bp.route('/list/settled', methods=['GET'])
@auth_required(min_role="premium_user")
def get_settled_debts_grouped():
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id'}), 400

    pipeline = [
        {'$match': {
            'status': {'$in': ['settled', 'canceled']},
            'account_id': account_id
        }},
        {'$group': {
            '_id': {'person': {'$toLower': '$person'}, 'currency': '$currency', 'type': '$type'},
            'person_display': {'$first': '$person'},
            'totalAmount': {'$sum': '$originalAmount'},
            'count': {'$sum': 1}
        }},
        {'$group': {
            '_id': {'person': '$_id.person', 'type': '$_id.type'},
            'person': {'$first': '$person_display'},
            'totals': {'$push': {'currency': '$_id.currency', 'total': '$totalAmount', 'count': '$count'}}
        }},
        {'$project': {'_id': 0, 'person': 1, 'type': '$_id.type', 'totals': 1}},
        {'$sort': {'person': 1}}
    ]
    return jsonify(list(debts_collection().aggregate(pipeline)))


@debts_bp.route('/<debt_id>', methods=['GET'])
@auth_required(min_role="premium_user")
def get_debt_details(debt_id):
    try:
        account_id = get_account_id()
        debt = debts_collection().find_one({'_id': ObjectId(debt_id), 'account_id': account_id})
        if not debt:
            return jsonify({'error': 'Debt not found'}), 404
        return jsonify(serialize_debt(debt))
    except Exception:
        return jsonify({'error': 'Invalid request'}), 400


@debts_bp.route('/person/<person_name>/<currency>', methods=['GET'])
@auth_required(min_role="premium_user")
def get_debts_by_person_and_currency(person_name, currency):
    return _get_debts_by_filter(person_name, {'currency': currency, 'status': 'open'})


@debts_bp.route('/person/<person_name>/all', methods=['GET'])
@auth_required(min_role="premium_user")
def get_all_debts_by_person(person_name):
    return _get_debts_by_filter(person_name, {'status': 'open'})


@debts_bp.route('/person/<person_name>/all/settled', methods=['GET'])
@auth_required(min_role="premium_user")
def get_all_settled_debts_by_person(person_name):
    return _get_debts_by_filter(person_name, {'status': {'$in': ['settled', 'canceled']}})


def _get_debts_by_filter(person_name, additional_filters):
    try:
        account_id = get_account_id()
        query = {
            'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
            'account_id': account_id,
            **additional_filters
        }
        debts = list(debts_collection().find(query).sort('created_at', 1))
        return jsonify([serialize_debt(d) for d in debts])
    except ValueError:
        return jsonify({'error': 'Invalid account_id'}), 400


@debts_bp.route('/person/<payment_currency>/repay', methods=['POST'])
@auth_required(min_role="premium_user")
def record_lump_sum_repayment(payment_currency):
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id'}), 400

    data = request.json
    if not all(k in data for k in ['amount', 'type', 'person']):
        return jsonify({'error': 'Missing fields'}), 400

    debt_type = data['type']
    person_name = data['person']

    try:
        payment_amount = float(data['amount'])
        if payment_amount <= 0: raise ValueError
    except ValueError:
        return jsonify({'error': 'Amount must be a positive number'}), 400

    timestamp = datetime.now(UTC_TZ)
    if data.get('timestamp'):
        try:
            timestamp = datetime.fromisoformat(data.get('timestamp'))
        except ValueError:
            pass  # Fallback to now

    # 1. Find Debts to Repay
    query_base = {
        'person': re.compile(f'^{re.escape(person_name)}$', re.IGNORECASE),
        'status': 'open',
        'type': debt_type,
        'account_id': account_id
    }

    # Try matching currency first
    debts = list(debts_collection().find({**query_base, 'currency': payment_currency}).sort('created_at', 1))
    debt_currency = payment_currency
    converted_amount = payment_amount

    # Fallback: Try alternate currency if no debts found
    if not debts:
        alt_currency = 'USD' if payment_currency == 'KHR' else 'KHR'
        debts = list(debts_collection().find({**query_base, 'currency': alt_currency}).sort('created_at', 1))

        if not debts:
            return jsonify({'error': f'No open {debt_type} debts found for {person_name}'}), 404

        debt_currency = alt_currency
        rate = get_user_khr_rate(account_id)

        if payment_currency == 'KHR':  # Debt is USD
            converted_amount = payment_amount / rate
        else:  # Debt is KHR
            converted_amount = payment_amount * rate

    # 2. Calculate Repayment Distribution
    total_debt = sum(d['remainingAmount'] for d in debts)
    interest = 0.0
    principal_payment = converted_amount

    if converted_amount > total_debt + 0.001:
        interest = converted_amount - total_debt
        principal_payment = total_debt

        # Record Interest Transaction
        cat = "Loan Interest" if debt_type == 'lent' else "Interest Expense"
        tx_type = "income" if debt_type == 'lent' else "expense"

        transactions_collection().insert_one({
            "account_id": account_id,
            "type": tx_type,
            "amount": interest,
            "currency": debt_currency,
            "categoryId": cat,
            "accountName": f"{debt_currency} Account",
            "description": f"Interest {'from' if debt_type == 'lent' else 'paid to'} {person_name}",
            "timestamp": timestamp
        })

    # 3. Update Debts (Bulk)
    bulk_ops = []
    left_to_pay = principal_payment

    for debt in debts:
        if left_to_pay <= 0: break

        pay_this = min(left_to_pay, debt['remainingAmount'])
        new_rem = debt['remainingAmount'] - pay_this
        status = 'settled' if new_rem <= 0.001 else 'open'

        bulk_ops.append(UpdateOne(
            {'_id': debt['_id']},
            {
                '$inc': {'remainingAmount': -pay_this},
                '$push': {'repayments': {'amount': pay_this, 'date': timestamp}},
                '$set': {'status': status}
            }
        ))
        left_to_pay -= pay_this

    if bulk_ops:
        debts_collection().bulk_write(bulk_ops)

    # 4. Record Repayment Transaction
    rep_cat = 'Debt Settled' if debt_type == 'lent' else 'Debt Repayment'
    rep_type = 'income' if debt_type == 'lent' else 'expense'

    transactions_collection().insert_one({
        "account_id": account_id,
        "type": rep_type,
        "amount": payment_amount,
        "currency": payment_currency,
        "categoryId": rep_cat,
        "accountName": f"{payment_currency} Account",
        "description": f"Repayment {'from' if debt_type == 'lent' else 'to'} {person_name}",
        "timestamp": timestamp
    })

    msg = f"✅ Repayment of {payment_amount:,.2f} {payment_currency} recorded."
    if interest > 0:
        msg += f" Includes {interest:,.2f} {debt_currency} interest."

    return jsonify({'message': msg})


@debts_bp.route('/<debt_id>/cancel', methods=['POST'])
@auth_required(min_role="premium_user")
def cancel_debt(debt_id):
    try:
        account_id = get_account_id()
        debt = debts_collection().find_one({'_id': ObjectId(debt_id), 'account_id': account_id})

        if not debt: return jsonify({'error': 'Debt not found'}), 404
        if debt['status'] == 'canceled': return jsonify({'error': 'Already canceled'}), 400

        # Reverse Transaction
        if tx_id := debt.get('associated_transaction_id'):
            orig = transactions_collection().find_one({'_id': ObjectId(tx_id)})
            if orig:
                reverse_type = 'income' if orig['type'] == 'expense' else 'expense'
                transactions_collection().insert_one({
                    "account_id": account_id,
                    "type": reverse_type,
                    "amount": orig['amount'],
                    "currency": orig['currency'],
                    "categoryId": "Canceled Debt",
                    "accountName": orig['accountName'],
                    "description": f"Reversal: {orig['description']}",
                    "timestamp": datetime.now(UTC_TZ)
                })

        debts_collection().update_one(
            {'_id': ObjectId(debt_id)},
            {'$set': {'status': 'canceled', 'remainingAmount': 0}}
        )
        return jsonify({'message': 'Debt canceled'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@debts_bp.route('/<debt_id>', methods=['PUT'])
@auth_required(min_role="premium_user")
def update_debt(debt_id):
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id'}), 400

    data = request.json
    updates = {}
    if 'person' in data: updates['person'] = data['person'].strip().title()
    if 'purpose' in data: updates['purpose'] = data['purpose'].strip()

    if not updates:
        return jsonify({'error': 'No valid fields'}), 400

    res = debts_collection().update_one(
        {'_id': ObjectId(debt_id), 'account_id': account_id},
        {'$set': updates}
    )

    if res.matched_count == 0:
        return jsonify({'error': 'Debt not found'}), 404

    return jsonify({'message': 'Debt updated'})


@debts_bp.route('/analysis', methods=['GET'])
@auth_required(min_role="premium_user")
def get_debt_analysis():
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id'}), 400

    rate = get_user_khr_rate(account_id)
    now = datetime.now(UTC_TZ)

    pipeline = [
        {'$match': {'status': 'open', 'account_id': account_id}},
        {'$facet': {
            'concentration': [
                {'$group': {
                    '_id': {'person': {'$toLower': '$person'}, 'type': '$type'},
                    'person': {'$first': '$person'},
                    'total': {'$sum': '$remainingAmount'}
                }},
                {'$sort': {'total': -1}},
                {'$project': {'_id': 0, 'person': 1, 'type': '$_id.type', 'total': 1}}
            ],
            'aging': [
                {'$project': {
                    'person': '$person',
                    'age': {'$divide': [{'$subtract': [now, '$created_at']}, 86400000]}
                }},
                {'$group': {
                    '_id': {'$toLower': '$person'},
                    'person': {'$first': '$person'},
                    'averageAgeDays': {'$avg': '$age'},
                    'count': {'$sum': 1}
                }},
                {'$sort': {'averageAgeDays': -1}},
                {'$project': {'_id': 0}}
            ],
            'overview': [
                {'$addFields': {
                    'usd_val': {
                        '$cond': [
                            {'$eq': ['$currency', 'USD']},
                            '$remainingAmount',
                            {'$divide': ['$remainingAmount', rate]}
                        ]
                    }
                }},
                {'$group': {'_id': '$type', 'total_usd': {'$sum': '$usd_val'}}}
            ]
        }}
    ]

    res = list(debts_collection().aggregate(pipeline))[0]

    overview_map = {item['_id']: item['total_usd'] for item in res.get('overview', [])}

    return jsonify({
        'concentration': res.get('concentration', []),
        'aging': res.get('aging', []),
        'overview_usd': {
            'total_lent_usd': overview_map.get('lent', 0),
            'total_borrowed_usd': overview_map.get('borrowed', 0)
        }
    })