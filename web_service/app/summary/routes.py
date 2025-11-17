from flask import Blueprint, jsonify, g
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from bson import ObjectId

from app.utils.db import get_db, settings_collection, transactions_collection, debts_collection
from app.utils.auth import auth_required
from app.utils.currency import get_live_usd_to_khr_rate

summary_bp = Blueprint('summary', __name__, url_prefix='/summary')

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")
FINANCIAL_CATS = ['Loan Lent', 'Debt Repayment', 'Loan Received', 'Debt Settled']


def get_account_id():
    try:
        return ObjectId(g.account_id)
    except Exception:
        raise ValueError("Invalid account_id format")


def get_date_ranges():
    """Returns UTC date ranges for the summary dashboard."""
    today = datetime.now(PHNOM_PENH_TZ).date()

    def to_utc(d_start, d_end):
        s = datetime.combine(d_start, time.min, tzinfo=PHNOM_PENH_TZ).astimezone(UTC_TZ)
        e = datetime.combine(d_end, time.max, tzinfo=PHNOM_PENH_TZ).astimezone(UTC_TZ)
        return s, e

    start_week = today - timedelta(days=today.weekday())
    start_month = today.replace(day=1)
    start_prev_month = (start_month - timedelta(days=1)).replace(day=1)
    end_prev_month = start_month - timedelta(days=1)

    return {
        "today": to_utc(today, today),
        "this_week": to_utc(start_week, start_week + timedelta(days=6)),
        "last_week": to_utc(start_week - timedelta(days=7), start_week - timedelta(days=1)),
        "this_month": to_utc(start_month,
                             (start_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)),
        "last_month": to_utc(start_prev_month, end_prev_month)
    }


@summary_bp.route('/detailed', methods=['GET'])
@auth_required(min_role="user")
def get_detailed_summary():
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id format'}), 400

    # 1. Fetch Settings
    user_settings = settings_collection().find_one({'account_id': account_id}, {'settings': 1})
    if not user_settings:
        return jsonify({'error': 'User settings not found'}), 404

    settings = user_settings.get('settings', {})
    initial_balances = settings.get('initial_balances', {})
    mode = settings.get('currency_mode', 'dual')

    currencies = ['USD'] if mode == 'single' else ['USD', 'KHR']
    if mode == 'single' and settings.get('primary_currency'):
        currencies = [settings.get('primary_currency')]

    # Determine Rate
    user_rate = 4100.0
    if settings.get('rate_preference') == 'fixed':
        user_rate = float(settings.get('fixed_rate', 4100.0))
    else:
        user_rate = get_live_usd_to_khr_rate()

    # 2. Calculate Balances (Aggregated Income/Expense)
    tx_totals = list(transactions_collection().aggregate([
        {'$match': {'account_id': account_id, 'currency': {'$in': currencies}}},
        {'$group': {'_id': {'type': '$type', 'currency': '$currency'}, 'total': {'$sum': '$amount'}}}
    ]))

    final_balances = {}
    for curr in currencies:
        base = initial_balances.get(curr, 0)
        inc = next((x['total'] for x in tx_totals if x['_id']['type'] == 'income' and x['_id']['currency'] == curr), 0)
        exp = next((x['total'] for x in tx_totals if x['_id']['type'] == 'expense' and x['_id']['currency'] == curr), 0)
        final_balances[curr] = base + inc - exp

    # 3. Calculate Debts
    debt_data = list(debts_collection().aggregate([
        {'$match': {'status': 'open', 'account_id': account_id, 'currency': {'$in': currencies}}},
        {'$group': {'_id': {'type': '$type', 'currency': '$currency'}, 'total': {'$sum': '$remainingAmount'}}}
    ]))

    owed_to_you = [{'total': d['total'], '_id': d['_id']['currency']} for d in debt_data if d['_id']['type'] == 'lent']
    owed_by_you = [{'total': d['total'], '_id': d['_id']['currency']} for d in debt_data if
                   d['_id']['type'] == 'borrowed']

    # 4. Period Summaries ($facet)
    ranges = get_date_ranges()
    min_date = min(r[0] for r in ranges.values())
    max_date = max(r[1] for r in ranges.values())

    conversion = {
        '$addFields': {
            'usd_val': {
                '$cond': [
                    {'$eq': ['$currency', 'USD']}, '$amount',
                    {'$divide': ['$amount', {'$ifNull': ['$exchangeRateAtTime', user_rate]}]}
                ]
            }
        }
    }

    facets = {}
    for name, (start, end) in ranges.items():
        facets[name] = [
            {'$match': {'timestamp': {'$gte': start, '$lte': end}}},
            {'$group': {
                '_id': {'type': '$type', 'currency': '$currency'},
                'total': {'$sum': '$amount'},
                'totalUSD': {'$sum': '$usd_val'}
            }}
        ]

    period_results = list(transactions_collection().aggregate([
        {'$match': {
            'timestamp': {'$gte': min_date, '$lte': max_date},
            'categoryId': {'$nin': FINANCIAL_CATS},
            'account_id': account_id
        }},
        conversion,
        {'$facet': facets}
    ]))[0]

    period_summaries = {}
    for name in ranges:
        data = period_results.get(name, [])
        summary = {'income': {}, 'expense': {}, 'net_usd': 0}
        inc_usd, exp_usd = 0, 0

        for item in data:
            t_type = item['_id']['type']
            curr = item['_id']['currency']
            summary[t_type][curr] = item['total']

            if t_type == 'income':
                inc_usd += item['totalUSD']
            else:
                exp_usd += item['totalUSD']

        summary['net_usd'] = inc_usd - exp_usd
        period_summaries[name] = summary

    return jsonify({
        'balances': final_balances,
        'debts_owed_by_you': owed_by_you,
        'debts_owed_to_you': owed_to_you,
        'periods': period_summaries
    })