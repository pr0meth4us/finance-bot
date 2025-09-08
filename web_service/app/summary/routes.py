# --- Start of modified file: web_service/app/summary/routes.py ---

from flask import Blueprint, jsonify, current_app
# --- MODIFICATION START ---
from datetime import datetime, time, date, timedelta
# --- MODIFICATION END ---

summary_bp = Blueprint('summary', __name__, url_prefix='/summary')

# --- MODIFICATION START ---
# Define categories to exclude from operational income/expense summaries.
# These categories affect balance but are not regular spending/earning.
FINANCIAL_TRANSACTION_CATEGORIES = [
    'Loan Lent',         # Expense type from lending money to someone
    'Debt Repayment',    # Expense type from repaying a debt you owed
    'Loan Received',     # Income type from borrowing money from someone
    'Debt Settled',      # Income type from someone repaying a debt to you
    'Initial Balance'    # Adjustment type for setting initial account value
]

def get_date_ranges():
    """Helper function to get start and end datetimes for various periods."""
    # In a production system with multiple users, we'd pass timezone from user.
    # For a personal bot, we assume server time or a fixed timezone.
    today = date.today()

    # This Week (assuming week starts on Monday)
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # This Month
    start_of_month = today.replace(day=1)
    next_month = start_of_month.replace(day=28) + timedelta(days=4)
    end_of_month = next_month - timedelta(days=next_month.day)

    return {
        "today": (datetime.combine(today, time.min), datetime.combine(today, time.max)),
        "this_week": (datetime.combine(start_of_week, time.min), datetime.combine(end_of_week, time.max)),
        "this_month": (datetime.combine(start_of_month, time.min), datetime.combine(end_of_month, time.max)),
    }

def calculate_operational_summary(start_date, end_date, db):
    """Calculates income/expense excluding financial adjustments."""
    pipeline = [
        {'$match': {
            'timestamp': {'$gte': start_date, '$lte': end_date},
            # Filter out loan/balance transactions
            'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES}
        }},
        {
            '$group': {
                '_id': {'type': '$type', 'currency': '$currency'},
                'total': {'$sum': '$amount'}
            }
        }
    ]
    results = list(db.transactions.aggregate(pipeline))

    period_summary = {
        'income': {},
        'expense': {}
    }
    for item in results:
        trans_type = item['_id']['type']
        currency = item['_id']['currency']
        if trans_type in period_summary:
            period_summary[trans_type][currency] = item['total']
    return period_summary
# --- MODIFICATION END ---


@summary_bp.route('/balance', methods=['GET'])
def get_balance_summary():
    db = current_app.db

    # 1. Calculate Total Balances (All transactions included to reflect true cash on hand)
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

    # 2. Calculate Open Debts (This logic remains separate)
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

    # --- MODIFICATION START ---
    # 3. Calculate Operational Period Summaries (Filtered logic applied here)
    date_ranges = get_date_ranges()
    period_summaries = {}
    for period, (start, end) in date_ranges.items():
        period_summaries[period] = calculate_operational_summary(start, end, db)
    # --- MODIFICATION END ---

    summary = {
        'balances': {'KHR': khr_balance, 'USD': usd_balance},
        'debts_owed_by_you': borrowed_results,
        'debts_owed_to_you': lent_results,
        # Add new period summary data to response
        'periods': period_summaries
    }

    return jsonify(summary)
# --- End of modified file: web_service/app/summary/routes.py ---