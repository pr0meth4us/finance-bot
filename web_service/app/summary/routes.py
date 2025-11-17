# --- web_service/app/summary/routes.py (Refactored) ---
"""
Handles the main summary endpoint for the bot.
All endpoints are multi-tenant and require a valid user_id.
"""
from flask import Blueprint, jsonify, g
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from app.utils.db import get_db, settings_collection, transactions_collection, debts_collection
from app.utils.auth import auth_required
from app.utils.currency import get_live_usd_to_khr_rate
from bson import ObjectId

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


@summary_bp.route('/detailed', methods=['GET'])
@auth_required(min_role="user")
def get_detailed_summary():
    """Generates the detailed summary for the authenticated user."""
    db = get_db()
    try:
        account_id = ObjectId(g.account_id)
    except Exception:
        return jsonify({'error': 'Invalid account_id format'}), 400

    # 1. Get User's Settings (Initial Balances, Mode, Currencies)
    # Optimization: Project only needed fields
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

    # Rate determination
    rate_preference = settings.get('rate_preference', 'live')
    user_rate = 4100.0
    if rate_preference == 'fixed':
        user_rate = settings.get('fixed_rate', 4100.0)
    else:
        user_rate = get_live_usd_to_khr_rate()

    # 2. Calculate Total Transaction Flow (Income & Expense)
    # This calculates the "lifetime" totals for the balance calculation
    pipeline_transactions = [
        {'$match': {
            'account_id': account_id,
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
        income = next((r['total'] for r in tx_results if
                       r['_id']['type'] == 'income' and r['_id']['currency'] == currency), 0)
        expense = next((r['total'] for r in tx_results if
                        r['_id']['type'] == 'expense' and r['_id']['currency'] == currency), 0)
        final_balances[currency] = initial + income - expense

    # 4. Calculate Debts
    pipeline_debts = [
        {'$match': {
            'status': 'open',
            'account_id': account_id,
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

    # 5. Calculate Period Summaries using $facet
    date_ranges = get_date_ranges()

    # Determine global min date to filter the initial match stage
    min_date = min(r[0] for r in date_ranges.values())
    max_date = max(r[1] for r in date_ranges.values())

    # Common stage for currency conversion
    conversion_stage = {
        '$addFields': {
            'amount_in_usd': {
                '$cond': {
                    'if': {'$eq': ['$currency', 'USD']},
                    'then': '$amount',
                    'else': {
                        '$let': {
                            'vars': {'rate': {'$ifNull': ['$exchangeRateAtTime', user_rate]}},
                            'in': {
                                '$cond': {
                                    'if': {'$gt': ['$$rate', 0]},
                                    'then': {'$divide': ['$amount', '$$rate']},
                                    'else': {'$divide': ['$amount', user_rate]}
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    group_stage = {
        '$group': {
            '_id': {'type': '$type', 'currency': '$currency'},
            'total': {'$sum': '$amount'},
            'totalUSD': {'$sum': '$amount_in_usd'}
        }
    }

    facet_stages = {}
    for period_name, (start_dt, end_dt) in date_ranges.items():
        facet_stages[period_name] = [
            {'$match': {'timestamp': {'$gte': start_dt, '$lte': end_dt}}},
            group_stage
        ]

    pipeline_periods = [
        {'$match': {
            'timestamp': {'$gte': min_date, '$lte': max_date},
            'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES},
            'account_id': account_id
        }},
        conversion_stage,
        {'$facet': facet_stages}
    ]

    facet_results = list(transactions_collection().aggregate(pipeline_periods))

    period_summaries = {}

    # Helper to process facet output
    def process_facet_result(results):
        summary = {'income': {}, 'expense': {}, 'net_usd': 0}
        total_income_usd = 0
        total_expense_usd = 0
        for item in results:
            trans_type = item['_id']['type']
            currency = item['_id']['currency']
            if trans_type in summary:
                summary[trans_type][currency] = item['total']

            if trans_type == 'income':
                total_income_usd += item['totalUSD']
            elif trans_type == 'expense':
                total_expense_usd += item['totalUSD']
        summary['net_usd'] = total_income_usd - total_expense_usd
        return summary

    if facet_results:
        facets = facet_results[0]
        for period in date_ranges.keys():
            raw_data = facets.get(period, [])
            period_summaries[period] = process_facet_result(raw_data)
    else:
        # Should not happen given list() behavior, but safe fallback
        for period in date_ranges.keys():
            period_summaries[period] = {'income': {}, 'expense': {}, 'net_usd': 0}

    # 6. Combine all data
    summary = {
        'balances': final_balances,
        'debts_owed_by_you': debts_owed_by_you,
        'debts_owed_to_you': debts_owed_to_you,
        'periods': period_summaries
    }

    return jsonify(summary)