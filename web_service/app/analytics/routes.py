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
    This endpoint returns JSON data instead of an image.
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

    # Common stages for converting amounts to USD
    add_fields_stage = {
        '$addFields': {
            'amount_in_usd': {
                '$cond': {
                    'if': {'$eq': ['$currency', 'USD']},
                    'then': '$amount',
                    'else': {  # Handle KHR
                        '$let': {
                            'vars': {
                                'rate': {'$ifNull': ['$exchangeRateAtTime', 4100.0]}
                            },
                            'in': {
                                '$cond': {
                                    'if': {'$gt': ['$$rate', 0]},
                                    'then': {'$divide': ['$amount', '$$rate']},
                                    'else': {'$divide': ['$amount', 4100.0]}
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    # Pipeline 1: Operational transactions (day-to-day income/expense)
    operational_pipeline = [
        {'$match': {
            'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc},
            'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES}
        }},
        add_fields_stage,
        {'$group': {
            '_id': {'type': '$type', 'category': '$categoryId'},
            'total': {'$sum': '$amount_in_usd'}
        }},
        {'$sort': {'total': -1}}
    ]

    # Pipeline 2: Financial transactions (loans, debts, etc.)
    financial_pipeline = [
        {'$match': {
            'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc},
            'categoryId': {'$in': FINANCIAL_TRANSACTION_CATEGORIES}
        }},
        add_fields_stage,
        {'$group': {
            '_id': '$categoryId',
            'total': {'$sum': '$amount_in_usd'}
        }}
    ]

    operational_data = list(current_app.db.transactions.aggregate(operational_pipeline))
    financial_data = list(current_app.db.transactions.aggregate(financial_pipeline))

    if not operational_data and not financial_data:
        return jsonify({"error": "No data found for the selected period."}), 404

    # Process the aggregated data
    report = {
        "startDate": start_date_local_obj.isoformat(),
        "endDate": end_date_local_obj.isoformat(),
        "summary": {
            "totalIncomeUSD": 0,
            "totalExpenseUSD": 0,
            "netSavingsUSD": 0
        },
        "financialSummary": {
            "totalLentUSD": 0,
            "totalBorrowedUSD": 0,
            "totalRepaidToYouUSD": 0,
            "totalYouRepaidUSD": 0
        },
        "incomeBreakdown": [],
        "expenseBreakdown": []
    }

    # Process operational data
    for item in operational_data:
        item_type = item['_id']['type']
        category = item['_id']['category']
        total = item['total']

        if item_type == 'income':
            report['summary']['totalIncomeUSD'] += total
            report['incomeBreakdown'].append({'category': category, 'totalUSD': total})
        elif item_type == 'expense':
            report['summary']['totalExpenseUSD'] += total
            report['expenseBreakdown'].append({'category': category, 'totalUSD': total})

    report['summary']['netSavingsUSD'] = report['summary']['totalIncomeUSD'] - report['summary']['totalExpenseUSD']

    # Process financial data
    for item in financial_data:
        category = item['_id']
        total = item['total']
        if category == 'Loan Lent':
            report['financialSummary']['totalLentUSD'] += total
        elif category == 'Loan Received':
            report['financialSummary']['totalBorrowedUSD'] += total
        elif category == 'Debt Settled':
            report['financialSummary']['totalRepaidToYouUSD'] += total
        elif category == 'Debt Repayment':
            report['financialSummary']['totalYouRepaidUSD'] += total

    return jsonify(report)


@analytics_bp.route('/habits', methods=['GET'])
def get_spending_habits():
    """
    Analyzes transaction data to provide insights into spending habits,
    including spending by time of day, day of week, and common keywords.
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
        else:  # Default to last 30 days if no range provided
            end_date_utc = datetime.now(UTC_TZ)
            start_date_utc = end_date_utc - timedelta(days=30)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date format."}), 400

    # --- START OF FIX ---
    # Define a reusable stage for currency conversion to USD
    add_fields_stage = {
        '$addFields': {
            'amount_in_usd': {
                '$cond': {
                    'if': {'$eq': ['$currency', 'USD']},
                    'then': '$amount',
                    'else': {  # Handle KHR
                        '$let': {
                            'vars': {
                                'rate': {'$ifNull': ['$exchangeRateAtTime', 4100.0]}
                            },
                            'in': {
                                '$cond': {
                                    'if': {'$gt': ['$$rate', 0]},
                                    'then': {'$divide': ['$amount', '$$rate']},
                                    'else': {'$divide': ['$amount', 4100.0]}
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    # --- END OF FIX ---

    # --- 1. Spending by Time of Day (FIXED) ---
    time_of_day_pipeline = [
        {'$match': {'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc}, 'type': 'expense'}},
        add_fields_stage,  # Apply currency conversion
        {'$bucket': {
            'groupBy': {'$hour': {'date': '$timestamp', 'timezone': 'Asia/Phnom_Penh'}},
            'boundaries': [0, 6, 12, 18, 24],
            'default': "Other",
            'output': {'totalAmount': {'$sum': '$amount_in_usd'}}  # Sum the converted amount
        }},
        {'$project': {
            '_id': 0,
            'period': {
                '$switch': {
                    'branches': [
                        {'case': {'$eq': ["$_id", 0]}, 'then': 'Late Night (12am-6am)'},
                        {'case': {'$eq': ["$_id", 6]}, 'then': 'Morning (6am-12pm)'},
                        {'case': {'$eq': ["$_id", 12]}, 'then': 'Afternoon (12pm-6pm)'},
                        {'case': {'$eq': ["$_id", 18]}, 'then': 'Evening (6pm-12am)'}
                    ]
                }
            },
            'total': '$totalAmount'
        }}
    ]

    # --- 2. Spending by Day of Week (FIXED) ---
    day_of_week_pipeline = [
        {'$match': {'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc}, 'type': 'expense'}},
        add_fields_stage,  # Apply currency conversion
        {'$group': {
            '_id': {'$dayOfWeek': {'date': '$timestamp', 'timezone': 'Asia/Phnom_Penh'}},
            'totalAmount': {'$sum': '$amount_in_usd'}  # Sum the converted amount
        }},
        {'$sort': {'_id': 1}},
        {'$project': {
            '_id': 0,
            'day': {
                '$switch': {
                    'branches': [
                        {'case': {'$eq': ["$_id", 1]}, 'then': 'Sunday'},
                        {'case': {'$eq': ["$_id", 2]}, 'then': 'Monday'},
                        {'case': {'$eq': ["$_id", 3]}, 'then': 'Tuesday'},
                        {'case': {'$eq': ["$_id", 4]}, 'then': 'Wednesday'},
                        {'case': {'$eq': ["$_id", 5]}, 'then': 'Thursday'},
                        {'case': {'$eq': ["$_id", 6]}, 'then': 'Friday'},
                        {'case': {'$eq': ["$_id", 7]}, 'then': 'Saturday'}
                    ]
                }
            },
            'total': '$totalAmount'
        }}
    ]

    # --- 3. Top Keywords per Category (FIXED PIPELINE) ---
    keywords_pipeline = [
        # Filter for relevant transactions that have a non-empty description
        {'$match': {
            'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc},
            'type': 'expense',
            'description': {'$exists': True, '$ne': ''}
        }},
        # Group by category and the lowercased description to count occurrences
        {'$group': {
            '_id': {
                'category': '$categoryId',
                'keyword': {'$toLower': '$description'}
            },
            'count': {'$sum': 1}
        }},
        # Sort by the count to get the most frequent keywords on top
        {'$sort': {'count': -1}},
        # Group again by just the category to roll up the keywords into a list
        {'$group': {
            '_id': '$_id.category',
            'topKeywordsWithCount': {
                '$push': {
                    'keyword': '$_id.keyword',
                    'count': '$count'
                }
            }
        }},
        # Project to the final desired shape
        {'$project': {
            '_id': 0,
            'category': '$_id',
            # Slice the array to get just the keyword strings of the top 3 items
            'topKeywords': {'$slice': ['$topKeywordsWithCount.keyword', 3]}
        }}
    ]

    habits = {
        'byTimeOfDay': list(current_app.db.transactions.aggregate(time_of_day_pipeline)),
        'byDayOfWeek': list(current_app.db.transactions.aggregate(day_of_week_pipeline)),
        'keywordsByCategory': list(current_app.db.transactions.aggregate(keywords_pipeline))
    }

    return jsonify(habits)
