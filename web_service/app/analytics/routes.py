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

    pipeline = [
        {'$match': {
            'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc},
            'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES}
        }},
        # --- START OF MODIFICATION ---
        # This stage is now more robust. It handles USD transactions directly,
        # and for KHR transactions, it checks if 'exchangeRateAtTime' exists and is valid.
        # If not, it falls back to a safe default (4100) to prevent division errors.
        {'$addFields': {
            'amount_in_usd': {
                '$cond': {
                    'if': {'$eq': ['$currency', 'USD']},
                    'then': '$amount',
                    'else': { # Handle KHR
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
        }},
        # --- END OF MODIFICATION ---
        {'$group': {
            '_id': {'type': '$type', 'category': '$categoryId'},
            'total': {'$sum': '$amount_in_usd'}
        }},
        {'$sort': {'total': -1}}
    ]

    data = list(current_app.db.transactions.aggregate(pipeline))

    if not data:
        return jsonify({"error": "No operational data found for the selected period."}), 404

    # Process the aggregated data
    report = {
        "startDate": start_date_local_obj.isoformat(),
        "endDate": end_date_local_obj.isoformat(),
        "summary": {
            "totalIncomeUSD": 0,
            "totalExpenseUSD": 0,
            "netSavingsUSD": 0
        },
        "incomeBreakdown": [],
        "expenseBreakdown": []
    }

    for item in data:
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

    return jsonify(report)
# --- End of modified file: web_service/app/analytics/routes.py ---