import re
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from flask import Blueprint, request, jsonify, g
from bson import ObjectId

from app.utils.db import get_db, settings_collection, transactions_collection
from app.utils.currency import get_live_usd_to_khr_rate
from app.utils.auth import auth_required
from app.analytics import pipelines

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")


def get_account_id():
    try:
        return ObjectId(g.account_id)
    except Exception:
        raise ValueError("Invalid account_id format")


def _get_user_financial_base(account_id):
    """Fetches user's initial balance in USD and their preferred rate."""
    doc = settings_collection().find_one(
        {'account_id': account_id},
        {'settings.initial_balances': 1, 'settings.rate_preference': 1, 'settings.fixed_rate': 1}
    )
    if not doc:
        raise Exception("User settings not found")

    settings = doc.get('settings', {})
    initial = settings.get('initial_balances', {})

    rate = get_live_usd_to_khr_rate()
    if settings.get('rate_preference') == 'fixed':
        rate = settings.get('fixed_rate', 4100.0)

    initial_usd = initial.get('USD', 0) + (initial.get('KHR', 0) / rate)
    return initial_usd, rate


def get_utc_range_for_period(period):
    """Helper to get UTC date ranges for named periods."""
    today = datetime.now(PHNOM_PENH_TZ).date()

    def to_utc(start, end):
        s = datetime.combine(start, time.min, tzinfo=PHNOM_PENH_TZ).astimezone(UTC_TZ)
        e = datetime.combine(end, time.max, tzinfo=PHNOM_PENH_TZ).astimezone(UTC_TZ)
        return s, e

    start_week = today - timedelta(days=today.weekday())
    start_month = today.replace(day=1)

    ranges = {
        "today": to_utc(today, today),
        "this_week": to_utc(start_week, start_week + timedelta(days=6)),
        "last_week": to_utc(start_week - timedelta(days=7), start_week - timedelta(days=1)),
        "this_month": to_utc(start_month,
                             (start_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1))
    }
    return ranges.get(period)


def parse_date_params(args):
    """Parses start/end date params or defaults to last 30 days."""
    s_str = args.get('start_date')
    e_str = args.get('end_date')

    if s_str and e_str:
        try:
            s_local = datetime.fromisoformat(s_str).date()
            e_local = datetime.fromisoformat(e_str).date()
            s_aware = datetime.combine(s_local, time.min, tzinfo=PHNOM_PENH_TZ)
            e_aware = datetime.combine(e_local, time.max, tzinfo=PHNOM_PENH_TZ)
            return s_aware.astimezone(UTC_TZ), e_aware.astimezone(UTC_TZ), s_local, e_local
        except ValueError:
            raise ValueError("Invalid date format")

    e_utc = datetime.now(UTC_TZ)
    s_utc = e_utc - timedelta(days=30)
    return s_utc, e_utc, s_utc.astimezone(PHNOM_PENH_TZ).date(), e_utc.astimezone(PHNOM_PENH_TZ).date()


@analytics_bp.route('/search', methods=['POST'])
@auth_required(min_role="premium_user")
def search_transactions():
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id format'}), 400

    params = request.json
    match_stage = {'account_id': account_id}
    date_filter = {}

    if params.get('period'):
        if r := get_utc_range_for_period(params['period']):
            date_filter = {'$gte': r[0], '$lte': r[1]}
    elif params.get('start_date') and params.get('end_date'):
        try:
            s_local = datetime.fromisoformat(params['start_date']).date()
            e_local = datetime.fromisoformat(params['end_date']).date()
            s_utc = datetime.combine(s_local, time.min, tzinfo=PHNOM_PENH_TZ).astimezone(UTC_TZ)
            e_utc = datetime.combine(e_local, time.max, tzinfo=PHNOM_PENH_TZ).astimezone(UTC_TZ)
            date_filter = {'$gte': s_utc, '$lte': e_utc}
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400

    if date_filter:
        match_stage['timestamp'] = date_filter

    if params.get('transaction_type'):
        match_stage['type'] = params['transaction_type']

    if params.get('categories'):
        cats = [re.compile(f'^{re.escape(c.strip())}$', re.IGNORECASE) for c in params['categories']]
        match_stage['categoryId'] = {'$in': cats}

    if params.get('keywords'):
        keywords = params['keywords']
        if params.get('keyword_logic', 'OR').upper() == 'AND':
            match_stage['$and'] = [{'description': re.compile(k, re.IGNORECASE)} for k in keywords]
        else:
            regex_str = '|'.join([re.escape(k) for k in keywords])
            match_stage['description'] = re.compile(regex_str, re.IGNORECASE)

    results = list(transactions_collection().aggregate(pipelines.build_search_pipeline(match_stage)))

    summary = {
        'total_count': 0,
        'totals_by_currency': [],
        'earliest_log_utc': None,
        'latest_log_utc': None
    }

    if not results:
        return jsonify(summary)

    min_dates, max_dates = [], []

    for res in results:
        summary['total_count'] += res['count']
        summary['totals_by_currency'].append({
            'currency': res['_id'],
            'count': res['count'],
            'total': res['totalAmount'],
            'avg': res['totalAmount'] / res['count'],
            'min': res['minAmount'],
            'max': res['maxAmount']
        })
        min_dates.append(res['minDate'])
        max_dates.append(res['maxDate'])

    if min_dates:
        summary['earliest_log_utc'] = min(min_dates).isoformat()
    if max_dates:
        summary['latest_log_utc'] = max(max_dates).isoformat()

    return jsonify(summary)


@analytics_bp.route('/report/detailed', methods=['GET'])
@auth_required(min_role="premium_user")
def get_detailed_report():
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id format'}), 400

    try:
        start_utc, end_utc, start_local, end_local = parse_date_params(request.args)
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    try:
        initial_usd, user_rate = _get_user_financial_base(account_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 404

    user_match = {'account_id': account_id}

    # 1. Start Balance
    start_bal_res = list(transactions_collection().aggregate(
        pipelines.build_start_balance_pipeline(start_utc, user_match, user_rate)
    ))
    start_inc = next((i['totalUSD'] for i in start_bal_res if i['_id'] == 'income'), 0)
    start_exp = next((i['totalUSD'] for i in start_bal_res if i['_id'] == 'expense'), 0)
    balance_at_start = initial_usd + start_inc - start_exp

    # 2. Faceted Report
    date_match = {'timestamp': {'$gte': start_utc, '$lte': end_utc}}
    facet_res = list(transactions_collection().aggregate(
        pipelines.build_faceted_report_pipeline(date_match, user_match, user_rate)
    ))

    facets = facet_res[0] if facet_res else {}

    report = {
        "startDate": start_local.isoformat(),
        "endDate": end_local.isoformat(),
        "summary": {
            "totalIncomeUSD": 0, "totalExpenseUSD": 0, "netSavingsUSD": 0,
            "balanceAtStartUSD": balance_at_start, "balanceAtEndUSD": 0
        },
        "financialSummary": {
            "totalLentUSD": 0, "totalBorrowedUSD": 0,
            "totalRepaidToYouUSD": 0, "totalYouRepaidUSD": 0
        },
        "incomeBreakdown": [],
        "expenseBreakdown": [],
        "spendingOverTime": facets.get('spending_over_time', []),
        "expenseInsights": {
            "topExpenseItem": facets.get('top_expense', [None])[0],
            "mostExpensiveDay": facets.get('daily_stats', [None])[0],
            "leastExpensiveDay": facets.get('daily_stats', [None])[-1] if facets.get('daily_stats') else None
        }
    }

    # Process Operational
    for item in facets.get('operational', []):
        cat_data = {'category': item['_id']['category'], 'totalUSD': item['total']}
        if item['_id']['type'] == 'income':
            report['summary']['totalIncomeUSD'] += item['total']
            report['incomeBreakdown'].append(cat_data)
        elif item['_id']['type'] == 'expense':
            report['summary']['totalExpenseUSD'] += item['total']
            report['expenseBreakdown'].append(cat_data)

    report['summary']['netSavingsUSD'] = report['summary']['totalIncomeUSD'] - report['summary']['totalExpenseUSD']

    # Process Financial
    fin_map = {
        'Loan Lent': 'totalLentUSD', 'Loan Received': 'totalBorrowedUSD',
        'Debt Settled': 'totalRepaidToYouUSD', 'Debt Repayment': 'totalYouRepaidUSD'
    }
    for item in facets.get('financial', []):
        if key := fin_map.get(item['_id']):
            report['financialSummary'][key] += item['total']

    # End Balance
    flow = facets.get('total_flow', [])
    flow_inc = next((i['totalUSD'] for i in flow if i['_id'] == 'income'), 0)
    flow_exp = next((i['totalUSD'] for i in flow if i['_id'] == 'expense'), 0)
    report['summary']['balanceAtEndUSD'] = balance_at_start + flow_inc - flow_exp

    return jsonify(report)


@analytics_bp.route('/habits', methods=['GET'])
@auth_required(min_role="premium_user")
def get_spending_habits():
    try:
        account_id = get_account_id()
    except ValueError:
        return jsonify({'error': 'Invalid account_id format'}), 400

    try:
        start_utc, end_utc, _, _ = parse_date_params(request.args)
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    try:
        _, user_rate = _get_user_financial_base(account_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 404

    day_pl, kw_pl = pipelines.build_habits_pipeline(start_utc, end_utc, {'account_id': account_id}, user_rate)

    return jsonify({
        'byDayOfWeek': list(transactions_collection().aggregate(day_pl)),
        'keywordsByCategory': list(transactions_collection().aggregate(kw_pl))
    })