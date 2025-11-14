# --- web_service/app/analytics/routes.py (Refactored) ---
"""
Handles all analytics and report generation endpoints.
All endpoints are multi-tenant and require a valid user_id.
"""
import io
from flask import Blueprint, Response, request, jsonify, g
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import re
from app.utils.db import get_db, settings_collection
from app.utils.currency import get_live_usd_to_khr_rate
# --- REFACTOR: Import new auth decorator ---
from app.utils.auth import auth_required

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

FINANCIAL_TRANSACTION_CATEGORIES = [
    'Loan Lent',
    'Debt Repayment',
    'Loan Received',
    'Debt Settled',
    'Initial Balance' # Kept for v1 data, but excluded from new reports
]

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")


def _get_user_financial_base(db, account_id):
    """
    Helper to get the user's initial balance in USD and their preferred rate.
    """
    # --- REFACTOR: Use 'db.settings' and query by 'account_id' ---
    user_settings_doc = settings_collection().find_one(
        {'account_id': account_id},
        {'settings': 1}
    )
    if not user_settings_doc:
        raise Exception("User settings not found")

    settings = user_settings_doc.get('settings', {})

    # Get initial balances
    initial_balances = settings.get('initial_balances', {})
    initial_usd = initial_balances.get('USD', 0)
    initial_khr = initial_balances.get('KHR', 0)

    # Get rate
    rate_preference = settings.get('rate_preference', 'live')
    rate = 4100.0
    if rate_preference == 'fixed':
        rate = settings.get('fixed_rate', 4100.0)
    else:
        rate = get_live_usd_to_khr_rate()

    # Calculate total initial balance in USD
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
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def search_transactions():
    """Performs an advanced search and sums up matching transactions for a user."""
    params = request.json
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    match_stage = {'account_id': account_id} # --- REFACTOR: Use account_id

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
    if params.get('categories'):
        categories_regex = [re.compile(f'^{re.escape(c.strip())}$', re.IGNORECASE) for c in params['categories']]
        match_stage['categoryId'] = {'$in': categories_regex}
    if params.get('keywords'):
        keywords = params['keywords']
        keyword_logic = params.get('keyword_logic', 'OR').upper()
        if keyword_logic == 'AND':
            match_stage['$and'] = [{'description': re.compile(k, re.IGNORECASE)} for k in keywords]
        else:
            regex_str = '|'.join([re.escape(k) for k in keywords])
            match_stage['description'] = re.compile(regex_str, re.IGNORECASE)

    pipeline = []
    if match_stage:
        pipeline.append({'$match': match_stage})

    pipeline.append({
        '$group': {
            '_id': '$currency',
            'totalAmount': {'$sum': '$amount'},
            'count': {'$sum': 1},
            'minAmount': {'$min': '$amount'},
            'maxAmount': {'$max': '$amount'},
            'minDate': {'$min': '$timestamp'},
            'maxDate': {'$max': '$timestamp'}
        }
    })

    results = list(db.transactions.aggregate(pipeline))

    if not results:
        return jsonify({'total_count': 0, 'totals_by_currency': []})

    overall_min_date = None
    overall_max_date = None

    summary = {
        'total_count': 0,
        'totals_by_currency': []
    }

    for res in results:
        currency = res['_id']
        count = res['count']
        total = res['totalAmount']

        if not overall_min_date or res['minDate'] < overall_min_date:
            overall_min_date = res['minDate']
        if not overall_max_date or res['maxDate'] > overall_max_date:
            overall_max_date = res['maxDate']

        summary['total_count'] += count
        summary['totals_by_currency'].append({
            'currency': currency,
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
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def get_detailed_report():
    """Generates a detailed report for the authenticated user."""
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

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
        # --- REFACTOR: Pass account_id ---
        initial_balance_in_usd, user_rate = _get_user_financial_base(db, account_id)
    except Exception as e:
        return jsonify({"error": f"Could not load user settings: {str(e)}"}), 404

    # --- REFACTOR: Use account_id ---
    user_match = {'account_id': account_id}

    add_fields_stage = {
        '$addFields': {
            'amount_in_usd': {
                '$cond': {
                    'if': {'$eq': ['$currency', 'USD']},
                    'then': '$amount',
                    'else': {
                        '$let': {
                            'vars': {'rate': {'$ifNull': ['$exchangeRateAtTime', user_rate]}}, # Use user's rate
                            'in': {'$cond': {'if': {'$gt': ['$$rate', 0]}, 'then': {'$divide': ['$amount', '$$rate']},
                                            'else': {'$divide': ['$amount', user_rate]}}}
                        }
                    }
                }
            }
        }
    }

    # --- Balance at Start Calculation ---
    start_balance_pipeline = [
        {'$match': {'timestamp': {'$lt': start_date_utc}, **user_match}},
        add_fields_stage,
        {'$group': {'_id': '$type', 'totalUSD': {'$sum': '$amount_in_usd'}}}
    ]
    start_balance_data = list(db.transactions.aggregate(start_balance_pipeline))
    start_income = next((item['totalUSD'] for item in start_balance_data if item['_id'] == 'income'), 0)
    start_expense = next((item['totalUSD'] for item in start_balance_data if item['_id'] == 'expense'), 0)

    # The starting balance is the Initial Balance + all transactions before the start date
    balance_at_start_usd = initial_balance_in_usd + start_income - start_expense

    # --- Pipelines for the selected period ---
    date_range_match = {'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc}}

    # Operational data (Exclude financial categories)
    operational_pipeline = [
        {'$match': {**date_range_match, 'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES}, **user_match}},
        add_fields_stage,
        {'$group': {'_id': {'type': '$type', 'category': '$categoryId'}, 'total': {'$sum': '$amount_in_usd'}}},
        {'$sort': {'total': -1}}
    ]

    # Financial data
    financial_pipeline = [
        {'$match': {**date_range_match, 'categoryId': {'$in': FINANCIAL_TRANSACTION_CATEGORIES}, **user_match}},
        add_fields_stage,
        {'$group': {'_id': '$categoryId', 'total': {'$sum': '$amount_in_usd'}}}
    ]

    # Total cash flow (Used for calculating end balance correctly)
    total_flow_pipeline = [
        {'$match': {**date_range_match, **user_match}},
        add_fields_stage,
        {'$group': {'_id': '$type', 'totalUSD': {'$sum': '$amount_in_usd'}}}
    ]

    # Spending Over Time
    spending_over_time_pipeline = [
        {'$match': {**date_range_match, 'type': 'expense', 'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES}, **user_match}},
        add_fields_stage,
        {
            '$project': {
                'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$timestamp', 'timezone': 'Asia/Phnom_Penh'}},
                'amount_in_usd': '$amount_in_usd'
            }
        },
        {'$group': {'_id': '$date', 'total_spent_usd': {'$sum': '$amount_in_usd'}}},
        {'$sort': {'_id': 1}},
        {'$project': {'_id': 0, 'date': '$_id', 'total_spent_usd': '$total_spent_usd'}}
    ]

    # Daily Expense Stats
    daily_stats_pipeline = [
        {'$match': {**date_range_match, 'type': 'expense', 'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES}, **user_match}},
        add_fields_stage,
        {
            '$group': {
                '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$timestamp', 'timezone': 'Asia/Phnom_Penh'}},
                'total_spent_usd': {'$sum': '$amount_in_usd'}
            }
        },
        {'$sort': {'total_spent_usd': -1}},
    ]

    # Top Expense Item
    top_expense_pipeline = [
        {'$match': {**date_range_match, 'type': 'expense', 'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES}, **user_match}},
        add_fields_stage,
        {'$sort': {'amount_in_usd': -1}},
        {'$limit': 1},
        {
            '$project': {
                '_id': 0,
                'description': '$description',
                'category': '$categoryId',
                'amount_usd': '$amount_in_usd',
                'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$timestamp', 'timezone': 'Asia/Phnom_Penh'}}
            }
        }
    ]

    # --- Execute All Pipelines ---
    operational_data = list(db.transactions.aggregate(operational_pipeline))
    financial_data = list(db.transactions.aggregate(financial_pipeline))
    total_flow_data = list(db.transactions.aggregate(total_flow_pipeline))
    spending_over_time_data = list(db.transactions.aggregate(spending_over_time_pipeline))
    daily_stats_data = list(db.transactions.aggregate(daily_stats_pipeline))
    top_expense_data = list(db.transactions.aggregate(top_expense_pipeline))

    # --- Assemble Report ---
    report = {
        "startDate": start_date_local_obj.isoformat(),
        "endDate": end_date_local_obj.isoformat(),
        "summary": {
            "totalIncomeUSD": 0, "totalExpenseUSD": 0, "netSavingsUSD": 0,
            "balanceAtStartUSD": balance_at_start_usd, "balanceAtEndUSD": 0
        },
        "financialSummary": {"totalLentUSD": 0, "totalBorrowedUSD": 0, "totalRepaidToYouUSD": 0,
                             "totalYouRepaidUSD": 0},
        "incomeBreakdown": [],
        "expenseBreakdown": [],
        "spendingOverTime": spending_over_time_data,
        "expenseInsights": {
            "topExpenseItem": top_expense_data[0] if top_expense_data else None,
            "mostExpensiveDay": daily_stats_data[0] if daily_stats_data else None,
            "leastExpensiveDay": daily_stats_data[-1] if daily_stats_data and (len(daily_stats_data) > 1 or daily_stats_data[0]['total_spent_usd'] > 0) else None
        }
    }

    # Populate Operational Summary
    for item in operational_data:
        if item['_id']['type'] == 'income':
            report['summary']['totalIncomeUSD'] += item['total']
            report['incomeBreakdown'].append({'category': item['_id']['category'], 'totalUSD': item['total']})
        elif item['_id']['type'] == 'expense':
            report['summary']['totalExpenseUSD'] += item['total']
            report['expenseBreakdown'].append({'category': item['_id']['category'], 'totalUSD': item['total']})
    report['summary']['netSavingsUSD'] = report['summary']['totalIncomeUSD'] - report['summary']['totalExpenseUSD']

    # Populate Financial Summary
    for item in financial_data:
        category_map = {
            'Loan Lent': 'totalLentUSD', 'Loan Received': 'totalBorrowedUSD',
            'Debt Settled': 'totalRepaidToYouUSD', 'Debt Repayment': 'totalYouRepaidUSD'
        }
        if item['_id'] in category_map:
            report['financialSummary'][category_map[item['_id']]] += item['total']

    # Calculate correct Ending Balance
    total_income_in_period = next((item['totalUSD'] for item in total_flow_data if item['_id'] == 'income'), 0)
    total_expense_in_period = next((item['totalUSD'] for item in total_flow_data if item['_id'] == 'expense'), 0)
    report['summary']['balanceAtEndUSD'] = balance_at_start_usd + total_income_in_period - total_expense_in_period

    return jsonify(report)


@analytics_bp.route('/habits', methods=['GET'])
@auth_required(min_role="premium_user") # --- REFACTOR: Add decorator ---
def get_spending_habits():
    """Analyzes spending habits for the authenticated user."""
    db = get_db()

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

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
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date format."}), 400

    try:
        # --- REFACTOR: Pass account_id ---
        _, user_rate = _get_user_financial_base(db, account_id)
    except Exception as e:
        return jsonify({"error": f"Could not load user settings: {str(e)}"}), 404

    # --- REFACTOR: Use account_id ---
    user_match = {'account_id': account_id}

    add_fields_stage = {
        '$addFields': {
            'amount_in_usd': {
                '$cond': {
                    'if': {'$eq': ['$currency', 'USD']},
                    'then': '$amount',
                    'else': {
                        '$let': {
                            'vars': {'rate': {'$ifNull': ['$exchangeRateAtTime', user_rate]}},
                            'in': {'$cond': {'if': {'$gt': ['$$rate', 0]}, 'then': {'$divide': ['$amount', '$$rate']},
                                            'else': {'$divide': ['$amount', user_rate]}}}
                        }
                    }
                }
            }
        }
    }

    day_of_week_pipeline = [
        {'$match': {'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc}, 'type': 'expense', **user_match}},
        add_fields_stage,
        {'$group': {
            '_id': {'$dayOfWeek': {'date': '$timestamp', 'timezone': 'Asia/Phnom_Penh'}},
            'totalAmount': {'$sum': '$amount_in_usd'}
        }},
        {'$sort': {'_id': 1}},
        {'$project': {
            '_id': 0,
            'day': {'$switch': {'branches': [
                {'case': {'$eq': ["$_id", 1]}, 'then': 'Sunday'},
                {'case': {'$eq': ["$_id", 2]}, 'then': 'Monday'},
                {'case': {'$eq': ["$_id", 3]}, 'then': 'Tuesday'},
                {'case': {'$eq': ["$_id", 4]}, 'then': 'Wednesday'},
                {'case': {'$eq': ["$_id", 5]}, 'then': 'Thursday'},
                {'case': {'$eq': ["$_id", 6]}, 'then': 'Friday'},
                {'case': {'$eq': ["$_id", 7]}, 'then': 'Saturday'}
            ]}},
            'total': '$totalAmount'
        }}
    ]

    keywords_pipeline = [
        {'$match': {
            'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc},
            'type': 'expense',
            'description': {'$exists': True, '$ne': ''},
            **user_match
        }},
        {'$group': {
            '_id': {'category': '$categoryId', 'keyword': {'$toLower': '$description'}},
            'count': {'$sum': 1}
        }},
        {'$sort': {'count': -1}},
        {'$group': {
            '_id': '$_id.category',
            'topKeywordsWithCount': {'$push': {'keyword': '$_id.keyword', 'count': '$count'}}
        }},
        {'$project': {
            '_id': 0, 'category': '$_id',
            'topKeywords': {'$slice': ['$topKeywordsWithCount.keyword', 3]}
        }}
    ]

    habits = {
        'byDayOfWeek': list(db.transactions.aggregate(day_of_week_pipeline)),
        'keywordsByCategory': list(db.transactions.aggregate(keywords_pipeline))
    }
    return jsonify(habits)