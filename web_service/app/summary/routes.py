# --- Start of modified file: web_service/app/summary/routes.py ---
"""
Handles the main summary endpoint for the bot.
All endpoints are multi-tenant and require a valid user_id.
"""
from flask import Blueprint, jsonify
from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo
from app import get_db
# --- MODIFICATION: Import the new auth helper ---
from app.utils.auth import get_user_id_from_request

summary_bp = Blueprint('summary', __name__, url_prefix='/summary')

FINANCIAL_TRANSACTION_CATEGORIES = [
    'Loan Lent',
    'Debt Repayment',
    'Loan Received',
    'Debt Settled',
    'Initial Balance'
]

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")

def create_utc_range(start_date_local, end_date_local):
    """Converts local start/end dates into a timezone-aware UTC range for querying."""
    aware_start_dt = datetime.combine(start_date_local, time.min, tzinfo=PHNOM_PENH_TZ)
    aware_end_dt = datetime.combine(end_date_local, time.max, tzinfo=PHNOM_PENH_TZ)
    return aware_start_dt.astimezone(UTC_TZ), aware_end_dt.astimezone(UTC_TZ)


def get_date_ranges():
    """Helper function to get start and end datetimes for various periods."""
    today = datetime.now(PHNOM_PENH_TZ).date()

    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    end_of_last_week = start_of_week - timedelta(days=1)
    start_of_last_week = end_of_last_week - timedelta(days=6)
    start_of_month = today.replace(day=1)
    next_month = start_of_month.replace(day=28) + timedelta(days=4)
    end_of_month = next_month - timedelta(days=next_month.day)
    end_of_last_month = start_of_month - timedelta(days=1)
    start_of_last_month = end_of_last_month.replace(day=1)

    return {
        "today": create_utc_range(today, today),
        "this_week": create_utc_range(start_of_week, end_of_week),
        "last_week": create_utc_range(start_of_last_week, end_of_last_week),
        "this_month": create_utc_range(start_of_month, end_of_month),
        "last_month": create_utc_range(start_of_last_month, end_of_last_month),
    }


def calculate_period_summary(start_date, end_date, db, user_id):
    """Helper to run aggregation for a specific time period for a specific user."""
    pipeline = [
        {'$match': {
            'timestamp': {'$gte': start_date, '$lte': end_date},
            'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES},
            'user_id': user_id # <-- MODIFICATION
        }},
        {
            '$addFields': {
                'amount_in_usd': {
                    '$cond': {
                        'if': {'$eq': ['$currency', 'USD']},
                        'then': '$amount',
                        'else': {
                            '$let': {
                                'vars': {'rate': {'$ifNull': ['$exchangeRateAtTime', 4100.0]}},
                                'in': {'$cond': {'if': {'$gt': ['$$rate', 0]}, 'then': {'$divide': ['$amount', '$$rate']}, 'else': {'$divide': ['$amount', 4100.0]}}}
                            }
                        }
                    }
                }
            }
        },
        {
            '$group': {
                '_id': {'type': '$type', 'currency': '$currency'},
                'total': {'$sum': '$amount'},
                'totalUSD': {'$sum': '$amount_in_usd'}
            }
        }
    ]
    results = list(db.transactions.aggregate(pipeline))

    period_summary = {
        'income': {}, 'expense': {}, 'net_usd': 0
    }
    total_income_usd = 0
    total_expense_usd = 0

    for item in results:
        trans_type = item['_id']['type']
        currency = item['_id']['currency']
        if trans_type in period_summary:
            period_summary[trans_type][currency] = item['total']

        if trans_type == 'income':
            total_income_usd += item['totalUSD']
        elif trans_type == 'expense':
            total_expense_usd += item['totalUSD']

    period_summary['net_usd'] = total_income_usd - total_expense_usd
    return period_summary


@summary_bp.route('/detailed', methods=['GET'])
def get_detailed_summary():
    """Generates the detailed summary for the authenticated user."""
    db = get_db()

    # --- MODIFICATION: Authenticate user ---
    user_id, error = get_user_id_from_request()
    if error: return error
    # ---

    # 1. Calculate Balances
    khr_pipeline = [
        {'$match': {'accountName': 'KHR Account', 'user_id': user_id}}, # <-- MODIFICATION
        {'$group': {'_id': '$type', 'total': {'$sum': '$amount'}}}
    ]
    khr_results = list(db.transactions.aggregate(khr_pipeline))
    khr_income = next((item['total'] for item in khr_results if item['_id'] == 'income'), 0)
    khr_expense = next((item['total'] for item in khr_results if item['_id'] == 'expense'), 0)
    khr_balance = khr_income - khr_expense

    usd_pipeline = [
        {'$match': {'accountName': 'USD Account', 'user_id': user_id}}, # <-- MODIFICATION
        {'$group': {'_id': '$type', 'total': {'$sum': '$amount'}}}
    ]
    usd_results = list(db.transactions.aggregate(usd_pipeline))
    usd_income = next((item['total'] for item in usd_results if item['_id'] == 'income'), 0)
    usd_expense = next((item['total'] for item in usd_results if item['_id'] == 'expense'), 0)
    usd_balance = usd_income - usd_expense

    # 2. Calculate Debts
    pipeline_debts = [
        {'$match': {'status': 'open', 'user_id': user_id}}, # <-- MODIFICATION
        {'$group': {
            '_id': {'type': '$type', 'currency': '$currency'},
            'totalAmount': {'$sum': '$remainingAmount'}
        }}
    ]
    debt_results = list(db.debts.aggregate(pipeline_debts))
    debts_owed_to_you = [d for d in debt_results if d['_id']['type'] == 'lent']
    debts_owed_by_you = [d for d in debt_results if d['_id']['type'] == 'borrowed']

    formatted_debts_to_you = [{'total': d['totalAmount'], '_id': d['_id']['currency']} for d in debts_owed_to_you]
    formatted_debts_by_you = [{'total': d['totalAmount'], '_id': d['_id']['currency']} for d in debts_owed_by_you]

    # 3. Calculate Period Summaries
    date_ranges = get_date_ranges()
    period_summaries = {}
    for period, (start_utc, end_utc) in date_ranges.items():
        period_summaries[period] = calculate_period_summary(start_utc, end_utc, db, user_id) # <-- MODIFICATION

    # 4. Combine all data
    summary = {
        'balances': {'KHR': khr_balance, 'USD': usd_balance},
        'debts_owed_by_you': formatted_debts_by_you,
        'debts_owed_to_you': formatted_debts_to_you,
        'periods': period_summaries
    }

    return jsonify(summary)
# --- End of modified file ---