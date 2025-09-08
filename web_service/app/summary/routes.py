# --- Start of modified file: web_service/app/summary/routes.py ---

from flask import Blueprint, jsonify, current_app
# --- MODIFICATION START ---
from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo
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

# Define local timezone for accurate date calculations
PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
# --- MODIFICATION END ---


def get_date_ranges():
    """Helper function to get start and end datetimes for various periods."""
    # --- MODIFICATION START: Use local timezone for date calculation ---
    # Fixes inconsistency where server date (UTC) differs from user's local date.
    today = datetime.now(PHNOM_PENH_TZ).date()
    # --- MODIFICATION END ---

    # This Week (assuming week starts on Monday)
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # Last Week
    end_of_last_week = start_of_week - timedelta(days=1)
    start_of_last_week = end_of_last_week - timedelta(days=6)

    # This Month
    start_of_month = today.replace(day=1)
    next_month = start_of_month.replace(day=28) + timedelta(days=4)
    end_of_month = next_month - timedelta(days=next_month.day)

    # Last Month
    end_of_last_month = start_of_month - timedelta(days=1)
    start_of_last_month = end_of_last_month.replace(day=1)

    return {
        "today": (datetime.combine(today, time.min), datetime.combine(today, time.max)),
        "this_week": (datetime.combine(start_of_week, time.min), datetime.combine(end_of_week, time.max)),
        "last_week": (datetime.combine(start_of_last_week, time.min), datetime.combine(end_of_last_week, time.max)),
        "this_month": (datetime.combine(start_of_month, time.min), datetime.combine(end_of_month, time.max)),
        "last_month": (datetime.combine(start_of_last_month, time.min), datetime.combine(end_of_last_month, time.max)),
    }


def calculate_period_summary(start_date, end_date, db):
    """Helper to run aggregation for a specific time period."""
    pipeline = [
        {'$match': {
            'timestamp': {'$gte': start_date, '$lte': end_date},
            # --- MODIFICATION START: Filter out non-operational transactions ---
            'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES}
            # --- MODIFICATION END ---
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


@summary_bp.route('/detailed', methods=['GET'])
def get_detailed_summary():
    db = current_app.db

    # 1. Calculate Balances (All transactions included to reflect true cash on hand)
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

    # 2. Calculate Debts (Data provided by a separate pipeline from the debts collection)
    pipeline_debts = [
        {'$match': {'status': 'open'}},
        {'$group': {
            '_id': {'type': '$type', 'currency': '$currency'},
            'totalAmount': {'$sum': '$remainingAmount'}
        }}
    ]
    debt_results = list(db.debts.aggregate(pipeline_debts))
    debts_owed_to_you = [d for d in debt_results if d['_id']['type'] == 'lent']
    debts_owed_by_you = [d for d in debt_results if d['_id']['type'] == 'borrowed']

    # Reformat debt data for frontend compatibility
    formatted_debts_to_you = [{'total': d['totalAmount'], '_id': d['_id']['currency']} for d in debts_owed_to_you]
    formatted_debts_by_you = [{'total': d['totalAmount'], '_id': d['_id']['currency']} for d in debts_owed_by_you]

    # 3. Calculate Period Summaries (Filtered logic applied via calculate_period_summary)
    date_ranges = get_date_ranges()
    period_summaries = {}
    for period, (start, end) in date_ranges.items():
        period_summaries[period] = calculate_period_summary(start, end, db)

    # 4. Combine all data
    summary = {
        'balances': {'KHR': khr_balance, 'USD': usd_balance},
        'debts_owed_by_you': formatted_debts_by_you,
        'debts_owed_to_you': formatted_debts_to_you,
        'periods': period_summaries
    }

    return jsonify(summary)
# --- End of modified file: web_service/app/summary/routes.py ---