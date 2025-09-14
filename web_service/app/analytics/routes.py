# --- Start of modified file: web_service/app/analytics/routes.py ---

import io
from flask import Blueprint, current_app, Response, request, jsonify
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

FINANCIAL_TRANSACTION_CATEGORIES = [
    'Loan Lent',
    'Debt Repayment',
    'Loan Received',
    'Debt Settled',
    'Initial Balance'
]

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")


@analytics_bp.route('/report/detailed', methods=['GET'])
def get_detailed_report():
    """
    Generates a detailed report with income/expense summaries and breakdowns.
    """
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

    add_fields_stage = {
        '$addFields': {
            'amount_in_usd': {
                '$cond': {
                    'if': {'$eq': ['$currency', 'USD']},
                    'then': '$amount',
                    'else': {
                        '$let': {
                            'vars': {'rate': {'$ifNull': ['$exchangeRateAtTime', 4100.0]}},
                            'in': {'$cond': {'if': {'$gt': ['$$rate', 0]}, 'then': {'$divide': ['$amount', '$$rate']},
                                             'else': {'$divide': ['$amount', 4100.0]}}}
                        }
                    }
                }
            }
        }
    }

    # --- START OF MODIFICATION: Calculate Starting Balance ---
    start_balance_pipeline = [
        {'$match': {'timestamp': {'$lt': start_date_utc}}},
        add_fields_stage,
        {'$group': {
            '_id': '$type',
            'totalUSD': {'$sum': '$amount_in_usd'}
        }}
    ]
    start_balance_data = list(current_app.db.transactions.aggregate(start_balance_pipeline))
    start_income = next((item['totalUSD'] for item in start_balance_data if item['_id'] == 'income'), 0)
    start_expense = next((item['totalUSD'] for item in start_balance_data if item['_id'] == 'expense'), 0)
    balance_at_start_usd = start_income - start_expense
    # --- END OF MODIFICATION ---

    operational_pipeline = [
        {'$match': {
            'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc},
            'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES}
        }},
        add_fields_stage,
        {'$group': {'_id': {'type': '$type', 'category': '$categoryId'}, 'total': {'$sum': '$amount_in_usd'}}},
        {'$sort': {'total': -1}}
    ]

    financial_pipeline = [
        {'$match': {
            'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc},
            'categoryId': {'$in': FINANCIAL_TRANSACTION_CATEGORIES}
        }},
        add_fields_stage,
        {'$group': {'_id': '$categoryId', 'total': {'$sum': '$amount_in_usd'}}}
    ]

    operational_data = list(current_app.db.transactions.aggregate(operational_pipeline))
    financial_data = list(current_app.db.transactions.aggregate(financial_pipeline))

    if not operational_data and not financial_data and not start_balance_data:
        return jsonify({"error": "No data found for the selected period."}), 404

    report = {
        "startDate": start_date_local_obj.isoformat(),
        "endDate": end_date_local_obj.isoformat(),
        "summary": {
            "totalIncomeUSD": 0, "totalExpenseUSD": 0, "netSavingsUSD": 0,
            "balanceAtStartUSD": balance_at_start_usd, "balanceAtEndUSD": 0  # Initialize new fields
        },
        "financialSummary": {"totalLentUSD": 0, "totalBorrowedUSD": 0, "totalRepaidToYouUSD": 0,
                             "totalYouRepaidUSD": 0},
        "incomeBreakdown": [], "expenseBreakdown": []
    }

    for item in operational_data:
        if item['_id']['type'] == 'income':
            report['summary']['totalIncomeUSD'] += item['total']
            report['incomeBreakdown'].append({'category': item['_id']['category'], 'totalUSD': item['total']})
        elif item['_id']['type'] == 'expense':
            report['summary']['totalExpenseUSD'] += item['total']
            report['expenseBreakdown'].append({'category': item['_id']['category'], 'totalUSD': item['total']})

    report['summary']['netSavingsUSD'] = report['summary']['totalIncomeUSD'] - report['summary']['totalExpenseUSD']

    # --- START OF MODIFICATION: Calculate Ending Balance ---
    report['summary']['balanceAtEndUSD'] = balance_at_start_usd + report['summary']['netSavingsUSD']
    # --- END OF MODIFICATION ---

    for item in financial_data:
        category_map = {
            'Loan Lent': 'totalLentUSD', 'Loan Received': 'totalBorrowedUSD',
            'Debt Settled': 'totalRepaidToYouUSD', 'Debt Repayment': 'totalYouRepaidUSD'
        }
        if item['_id'] in category_map:
            report['financialSummary'][category_map[item['_id']]] += item['total']

    return jsonify(report)


@analytics_bp.route('/habits', methods=['GET'])
def get_spending_habits():
    """
    Analyzes transaction data to provide insights into spending habits.
    """
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

    add_fields_stage = {
        '$addFields': {
            'amount_in_usd': {
                '$cond': {
                    'if': {'$eq': ['$currency', 'USD']},
                    'then': '$amount',
                    'else': {
                        '$let': {
                            'vars': {'rate': {'$ifNull': ['$exchangeRateAtTime', 4100.0]}},
                            'in': {'$cond': {'if': {'$gt': ['$$rate', 0]}, 'then': {'$divide': ['$amount', '$$rate']},
                                             'else': {'$divide': ['$amount', 4100.0]}}}
                        }
                    }
                }
            }
        }
    }

    time_of_day_pipeline = [
        {'$match': {'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc}, 'type': 'expense'}},
        add_fields_stage,
        {'$bucket': {
            'groupBy': {'$hour': {'date': '$timestamp', 'timezone': 'Asia/Phnom_Penh'}},
            'boundaries': [0, 6, 12, 18, 24],
            'default': "Other",
            'output': {'totalAmount': {'$sum': '$amount_in_usd'}}
        }},
        {'$project': {
            '_id': 0,
            'period': {'$switch': {'branches': [
                {'case': {'$eq': ["$_id", 0]}, 'then': 'Late Night (12am-6am)'},
                {'case': {'$eq': ["$_id", 6]}, 'then': 'Morning (6am-12pm)'},
                {'case': {'$eq': ["$_id", 12]}, 'then': 'Afternoon (12pm-6pm)'},
                {'case': {'$eq': ["$_id", 18]}, 'then': 'Evening (6pm-12am)'}
            ]}},
            'total': '$totalAmount'
        }}
    ]

    day_of_week_pipeline = [
        {'$match': {'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc}, 'type': 'expense'}},
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
            'description': {'$exists': True, '$ne': ''}
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
        'byTimeOfDay': list(current_app.db.transactions.aggregate(time_of_day_pipeline)),
        'byDayOfWeek': list(current_app.db.transactions.aggregate(day_of_week_pipeline)),
        'keywordsByCategory': list(current_app.db.transactions.aggregate(keywords_pipeline))
    }
    return jsonify(habits)