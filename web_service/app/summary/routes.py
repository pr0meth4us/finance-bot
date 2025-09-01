from flask import Blueprint, jsonify, current_app

summary_bp = Blueprint('summary', __name__, url_prefix='/summary')


@summary_bp.route('/balance', methods=['GET'])
def get_balance_summary():
    db = current_app.db

    khr_pipeline = [
        {'$match': {'accountName': 'KHR Account'}},
        {'$group': {'_id': '$type', 'total': {'$sum': '$amount'}}}
    ]
    khr_results = list(db.transactions.aggregate(khr_pipeline))
    khr_income = next((item['total'] for item in khr_results if item['_id'] == 'income'), 0)
    khr_expense = next((item['total'] for item in khr_results if item['_id'] == 'expense'), 0)
    khr_balance = khr_income - khr_expense

    usd_pipeline = [
        {'$match': {'accountName': 'USD Account'}},
        {'$group': {'_id': '$type', 'total': {'$sum': '$amount'}}}
    ]
    usd_results = list(db.transactions.aggregate(usd_pipeline))
    usd_income = next((item['total'] for item in usd_results if item['_id'] == 'income'), 0)
    usd_expense = next((item['total'] for item in usd_results if item['_id'] == 'expense'), 0)
    usd_balance = usd_income - usd_expense

    borrowed_pipeline = [
        {'$match': {'status': 'open', 'type': 'borrowed'}},
        {'$group': {'_id': '$currency', 'total': {'$sum': '$remainingAmount'}}}
    ]
    borrowed_results = list(db.debts.aggregate(borrowed_pipeline))

    lent_pipeline = [
        {'$match': {'status': 'open', 'type': 'lent'}},
        {'$group': {'_id': '$currency', 'total': {'$sum': '$remainingAmount'}}}
    ]
    lent_results = list(db.debts.aggregate(lent_pipeline))

    summary = {
        'balances': {'KHR': khr_balance, 'USD': usd_balance},
        'debts_owed_by_you': borrowed_results,
        'debts_owed_to_you': lent_results
    }

    return jsonify(summary)