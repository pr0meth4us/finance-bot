import io
import re
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from app.utils.db import get_db, settings_collection
from app.utils.currency import get_live_usd_to_khr_rate
from app.utils.auth import auth_required
from app.analytics import pipelines

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")


def _get_user_financial_base(account_id):
    """Helper to get the user's initial balance in USD and their preferred rate."""
    # Optimization: Use projection to fetch only necessary fields
    user_settings_doc = settings_collection().find_one(
        {'account_id': account_id},
        {'settings.initial_balances': 1, 'settings.rate_preference': 1, 'settings.fixed_rate': 1}
    )
    if not user_settings_doc:
        raise Exception("User settings not found")

    settings = user_settings_doc.get('settings', {})
    initial_balances = settings.get('initial_balances', {})
    initial_usd = initial_balances.get('USD', 0)
    initial_khr = initial_balances.get('KHR', 0)

    rate_preference = settings.get('rate_preference', 'live')
    if rate_preference == 'fixed':
        rate = settings.get('fixed_rate', 4100.0)
    else:
        rate = get_live_usd_to_khr_rate()

    initial_balance_in_usd = initial_usd + (initial_khr / rate)
    return initial_balance_in_usd, rate


def get_date_ranges_for_search():
    """Helper for analytics endpoints to get UTC date ranges."""
    today = datetime.now(PHNOM_PENH_TZ).date()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    end_of_last_week = start_of_week - timedelta(days=1)
    start_of_last_week = end_of_last_week - timedelta(days=6)

    def create_utc_range(start_local, end_local):
        aware_start = datetime.combine(start_local, time.min, tzinfo=PHNOM_PENH_TZ)
        aware_end = datetime.combine(end_local, time.max, tzinfo=PHNOM_PENH_TZ)
        return aware_start.astimezone(UTC_TZ), aware_end.astimezone(UTC_TZ)

    return {
        "today": create_utc_range(today, today),
        "this_week": create_utc_range(start_of_week, start_of_week + timedelta(days=6)),
        "last_week": create_utc_range(start_of_last_week, end_of_last_week),
        "this_month": create_utc_range(start_of_month,
                                       (start_of_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(
                                           days=1))
    }


@analytics_bp.route('/search', methods=['POST'])
@auth_required(min_role="premium_user")
def search_transactions():
    params = request.json
    db = get_db()

    try:
        account_id = ObjectId(g.account_id)
    except Exception:
        return jsonify({'error': 'Invalid account_id format'}), 400

    match_stage = {'account_id': account_id}
    date_filter = {}

    if params.get('period'):
        ranges = get_date_ranges_for_search()
        if params['period'] in ranges:
            start_utc, end_utc = ranges[params['period']]
            date_filter['$gte'] = start_utc
            date_filter['$lte'] = end_utc
    elif params.get('start_date') and params.get('end_date'):
        start_local = datetime.fromisoformat(params['start_date']).date()
        end_local = datetime.fromisoformat(params['end_date']).date()
        aware_start = datetime.combine(start_local, time.min, tzinfo=PHNOM_PENH_TZ)
        aware_end = datetime.combine(end_local, time.max, tzinfo=PHNOM_PENH_TZ)
        date_filter['$gte'] = aware_start.astimezone(UTC_TZ)
        date_filter['$lte'] = aware_end.astimezone(UTC_TZ)

    if date_filter:
        match_stage['timestamp'] = date_filter
    if params.get('transaction_type'):
        match_stage['type'] = params['transaction_type']

    # Optimize Regex: Compile once and use $in if possible
    if params.get('categories'):
        # Use a single $in with regexes, MongoDB supports this
        categories_regex = [re.compile(f'^{re.escape(c.strip())}$', re.IGNORECASE) for c in params['categories']]
        match_stage['categoryId'] = {'$in': categories_regex}

    if params.get('keywords'):
        keywords = params['keywords']
        keyword_logic = params.get('keyword_logic', 'OR').upper()
        if keyword_logic == 'AND':
            match_stage['$and'] = [{'description': re.compile(k, re.IGNORECASE)} for k in keywords]
        else:
            # Optimization: Combine OR keywords into a single regex
            regex_str = '|'.join([re.escape(k) for k in keywords])
            match_stage['description'] = re.compile(regex_str, re.IGNORECASE)

    pipeline = pipelines.build_search_pipeline(match_stage)
    results = list(db.transactions.aggregate(pipeline))

    if not results:
        return jsonify({'total_count': 0, 'totals_by_currency': []})

    summary = {'total_count': 0, 'totals_by_currency': []}
    overall_min_date = None
    overall_max_date = None

    for res in results:
        count = res['count']
        total = res['totalAmount']
        if not overall_min_date or res['minDate'] < overall_min_date:
            overall_min_date = res['minDate']
        if not overall_max_date or res['maxDate'] > overall_max_date:
            overall_max_date = res['maxDate']

        summary['total_count'] += count
        summary['totals_by_currency'].append({
            'currency': res['_id'],
            'count': count,
            'total': total,
            'avg': total / count,
            'min': res['minAmount'],
            'max': res['maxAmount']
        })

    summary['earliest_log_utc'] = overall_min_date.isoformat() if overall_min_date else None
    summary['latest_log_utc'] = overall_max_date.isoformat() if overall_max_date else None

    return jsonify(summary)


@analytics_bp.route('/report/detailed', methods=['GET'])
@auth_required(min_role="premium_user")
def get_detailed_report():
    db = get_db()
    try:
        account_id = ObjectId(g.account_id)
    except Exception:
        return jsonify({'error': 'Invalid account_id format'}), 400

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    try:
        if start_date_str and end_date_str:
            start_date_local_obj = datetime.fromisoformat(start_date_str).date()
            end_date_local_obj = datetime.fromisoformat(end_date_str).date()
            aware_start_local = datetime.combine(start_date_local_obj, time.min, tzinfo=PHNOM_PENH_TZ)
            aware_end_local = datetime.combine(end_date_local_obj, time.max, tzinfo=PHNOM_PENH_TZ)
            start_date_utc = aware_start_local.astimezone(UTC_TZ)
            end_date_utc = aware_end_local.astimezone(UTC_TZ)
        else:
            end_date_utc = datetime.now(UTC_TZ)
            start_date_utc = end_date_utc - timedelta(days=30)
            start_date_local_obj = (end_date_utc - timedelta(days=30)).astimezone(PHNOM_PENH_TZ).date()
            end_date_local_obj = end_date_utc.astimezone(PHNOM_PENH_TZ).date()
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    try:
        initial_balance_in_usd, user_rate = _get_user_financial_base(account_id)
    except Exception as e:
        return jsonify({"error": f"Could not load user settings: {str(e)}"}), 404

    user_match = {'account_id': account_id}

    # 1. Calculate Start Balance (Must be separate because it covers time < start_date)
    start_bal_pipeline = pipelines.build_start_balance_pipeline(start_date_utc, user_match, user_rate)
    start_balance_data = list(db.transactions.aggregate(start_bal_pipeline))

    start_income = next((item['totalUSD'] for item in start_balance_data if item['_id'] == 'income'), 0)
    start_expense = next((item['totalUSD'] for item in start_balance_data if item['_id'] == 'expense'), 0)
    balance_at_start_usd = initial_balance_in_usd + start_income - start_expense

    # 2. Run the Faceted Pipeline (Covers time >= start_date & <= end_date)
    date_range_match = {'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc}}
    facet_pipeline = pipelines.build_faceted_report_pipeline(date_range_match, user_match, user_rate)

    # Aggregation result comes as a single document with fields for each facet
    facet_results = list(db.transactions.aggregate(facet_pipeline))

    if facet_results:
        facets = facet_results[0]
        operational_data = facets.get('operational', [])
        financial_data = facets.get('financial', [])
        total_flow_data = facets.get('total_flow', [])
        spending_data = facets.get('spending_over_time', [])
        daily_stats_data = facets.get('daily_stats', [])
        top_expense_data = facets.get('top_expense', [])
    else:
        # Fallback for empty result set (shouldn't happen with $facet unless match fails completely)
        operational_data = []
        financial_data = []
        total_flow_data = []
        spending_data = []
        daily_stats_data = []
        top_expense_data = []

    report = {
        "startDate": start_date_local_obj.isoformat(),
        "endDate": end_date_local_obj.isoformat(),
        "summary": {
            "totalIncomeUSD": 0, "totalExpenseUSD": 0, "netSavingsUSD": 0,
            "balanceAtStartUSD": balance_at_start_usd, "balanceAtEndUSD": 0
        },
        "financialSummary": {
            "totalLentUSD": 0, "totalBorrowedUSD": 0,
            "totalRepaidToYouUSD": 0, "totalYouRepaidUSD": 0
        },
        "incomeBreakdown": [],
        "expenseBreakdown": [],
        "spendingOverTime": spending_data,
        "expenseInsights": {
            "topExpenseItem": top_expense_data[0] if top_expense_data else None,
            "mostExpensiveDay": daily_stats_data[0] if daily_stats_data else None,
            "leastExpensiveDay": daily_stats_data[-1] if daily_stats_data and (
                    len(daily_stats_data) > 1 or daily_stats_data[0]['total_spent_usd'] > 0) else None
        }
    }

    # Process Operational Data
    for item in operational_data:
        if item['_id']['type'] == 'income':
            report['summary']['totalIncomeUSD'] += item['total']
            report['incomeBreakdown'].append({'category': item['_id']['category'], 'totalUSD': item['total']})
        elif item['_id']['type'] == 'expense':
            report['summary']['totalExpenseUSD'] += item['total']
            report['expenseBreakdown'].append({'category': item['_id']['category'], 'totalUSD': item['total']})

    report['summary']['netSavingsUSD'] = report['summary']['totalIncomeUSD'] - report['summary']['totalExpenseUSD']

    # Process Financial Data
    category_map = {
        'Loan Lent': 'totalLentUSD', 'Loan Received': 'totalBorrowedUSD',
        'Debt Settled': 'totalRepaidToYouUSD', 'Debt Repayment': 'totalYouRepaidUSD'
    }
    for item in financial_data:
        cat_id = item['_id']
        if cat_id in category_map:
            report['financialSummary'][category_map[cat_id]] += item['total']

    # Process End Balance
    total_income_period = next((item['totalUSD'] for item in total_flow_data if item['_id'] == 'income'), 0)
    total_expense_period = next((item['totalUSD'] for item in total_flow_data if item['_id'] == 'expense'), 0)
    report['summary']['balanceAtEndUSD'] = balance_at_start_usd + total_income_period - total_expense_period

    return jsonify(report)


@analytics_bp.route('/habits', methods=['GET'])
@auth_required(min_role="premium_user")
def get_spending_habits():
    db = get_db()
    try:
        account_id = ObjectId(g.account_id)
    except Exception:
        return jsonify({'error': 'Invalid account_id format'}), 400

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    try:
        if start_date_str and end_date_str:
            start_date_local_obj = datetime.fromisoformat(start_date_str).date()
            end_date_local_obj = datetime.fromisoformat(end_date_str).date()
            aware_start = datetime.combine(start_date_local_obj, time.min, tzinfo=PHNOM_PENH_TZ)
            aware_end = datetime.combine(end_date_local_obj, time.max, tzinfo=PHNOM_PENH_TZ)
            start_date_utc = aware_start.astimezone(UTC_TZ)
            end_date_utc = aware_end.astimezone(UTC_TZ)
        else:
            end_date_utc = datetime.now(UTC_TZ)
            start_date_utc = end_date_utc - timedelta(days=30)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date format."}), 400

    try:
        _, user_rate = _get_user_financial_base(account_id)
    except Exception as e:
        return jsonify({"error": f"Could not load user settings: {str(e)}"}), 404

    user_match = {'account_id': account_id}
    day_pipeline, kw_pipeline = pipelines.build_habits_pipeline(start_date_utc, end_date_utc, user_match, user_rate)

    # Run these sequentially for now as they have different groupings.
    # Faceting them is possible but they have different sort stages that complicate it slightly.
    # Given low frequency of habits check, sequential is acceptable here.
    habits = {
        'byDayOfWeek': list(db.transactions.aggregate(day_pipeline)),
        'keywordsByCategory': list(db.transactions.aggregate(kw_pipeline))
    }
    return jsonify(habits)