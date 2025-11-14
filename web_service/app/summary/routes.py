# --- web_service/app/summary/routes.py (Refactored) ---
"""
Handles the main summary endpoint for the bot.
All endpoints are multi-tenant and require a valid user_id.
"""
from flask import Blueprint, jsonify, g
from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo
from app.utils.db import get_db, settings_collection, transactions_collection, debts_collection
# --- REFACTOR: Import new auth decorator ---
from app.utils.auth import auth_required
from app.utils.currency import get_live_usd_to_khr_rate

summary_bp = Blueprint('summary', __name__, url_prefix='/summary')

FINANCIAL_TRANSACTION_CATEGORIES = [
    'Loan Lent',
    'Debt Repayment',
    'Loan Received',
    'Debt Settled'
]

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")


def create_utc_range(start_date_local, end_date_local):
    """Converts local start/end dates into a timezone-aware UTC range."""
    aware_start_dt = datetime.combine(
        start_date_local, time.min, tzinfo=PHNOM_PENH_TZ
    )
    aware_end_dt = datetime.combine(
        end_date_local, time.max, tzinfo=PHNOM_PENH_TZ
    )
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


def calculate_period_summary(start_date, end_date, db, account_id, user_rate):
    """Helper to run aggregation for a specific time period for a user."""
    pipeline = [
        {'$match': {
            'timestamp': {'$gte': start_date, '$lte': end_date},
            'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES},
            'account_id': account_id # <-- REFACTOR
        }},
        {
            '$addFields': {
                'amount_in_usd': {
                    '$cond': {
                        'if': {'$eq': ['$currency', 'USD']},
                        'then': '$amount',
                        'else': {
                            '$let': {
                                'vars': {'rate': {'$ifNull': [
                                    '$exchangeRateAtTime', user_rate
                                ]}},
                                'in': {'$cond': {
                                    'if': {'$gt': ['$$rate', 0]},
                                    'then': {'$divide': ['$amount', '$$rate']},
                                    'else': {'$divide': ['$amount', user_rate]}
                                }}
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
    results = list(transactions_collection().aggregate(pipeline))

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
@auth_required(min_role="user") # --- REFACTOR: Add decorator ---
def get_detailed_summary():
    """Generates the detailed summary for the authenticated user."""
    db = get_db()
    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    # 1. Get User's Settings (Initial Balances, Mode, Currencies)
    # --- REFACTOR: Use 'db.settings' and query by 'account_id' ---
    user_settings_doc = settings_collection().find_one(
        {'account_id': account_id},
        {'settings': 1}
    )
    if not user_settings_doc:
        return jsonify({'error': 'User settings not found'}), 404

    settings = user_settings_doc.get('settings', {})
    initial_balances = settings.get('initial_balances', {})
    mode = settings.get('currency_mode', 'dual')

    currencies_to_track = []
    if mode == 'single':
        currencies_to_track.append(settings.get('primary_currency', 'USD'))
    else:
        currencies_to_track = ['USD', 'KHR']

    # 2. Calculate Total Transaction Flow (Income & Expense)
    pipeline_transactions = [
        {'$match': {
            'account_id': account_id, # <-- REFACTOR
            'currency': {'$in': currencies_to_track}
        }},
        {'$group': {
            '_id': {'type': '$type', 'currency': '$currency'},
            'total': {'$sum': '$amount'}
        }}
    ]
    tx_results = list(transactions_collection().aggregate(pipeline_transactions))

    # 3. Calculate Balances
    final_balances = {}
    for currency in currencies_to_track:
        initial = initial_balances.get(currency, 0)
        income = next((r['total'] for r in tx_results if r['_id']['type'] == 'income' and r['_id']['currency'] == currency), 0)
        expense = next((r['total'] for r in tx_results if r['_id']['type'] == 'expense' and r['_id']['currency'] == currency), 0)
        final_balances[currency] = initial + income - expense

    # 4. Calculate Debts
    pipeline_debts = [
        {'$match': {
            'status': 'open',
            'account_id': account_id, # <-- REFACTOR
            'currency': {'$in': currencies_to_track}
        }},
        {'$group': {
            '_id': {'type': '$type', 'currency': '$currency'},
            'totalAmount': {'$sum': '$remainingAmount'}
        }}
    ]
    debt_results = list(debts_collection().aggregate(pipeline_debts))

    debts_owed_to_you = [
        {'total': d['totalAmount'], '_id': d['_id']['currency']}
        for d in debt_results if d['_id']['type'] == 'lent'
    ]
    debts_owed_by_you = [
        {'total': d['totalAmount'], '_id': d['_id']['currency']}
        for d in debt_results if d['_id']['type'] == 'borrowed'
    ]

    # 5. Calculate Period Summaries

    # Get user's rate for period calculations
    rate_preference = settings.get('rate_preference', 'live')
    user_rate = 4100.0
    if rate_preference == 'fixed':
        user_rate = settings.get('fixed_rate', 4100.0)
    else:
        user_rate = get_live_usd_to_khr_rate() # Simplified for summary

    date_ranges = get_date_ranges()
    period_summaries = {}
    for period, (start_utc, end_utc) in date_ranges.items():
        period_summaries[period] = calculate_period_summary(
            start_utc, end_utc, db, account_id, user_rate
        )

    # 6. Combine all data
    summary = {
        'balances': final_balances,
        'debts_owed_by_you': debts_owed_by_you,
        'debts_owed_to_you': debts_owed_to_you,
        'periods': period_summaries
    }

    return jsonify(summary)