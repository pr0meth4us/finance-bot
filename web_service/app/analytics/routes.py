# --- Start of modified file: web_service/app/analytics/routes.py ---

import io
from flask import Blueprint, current_app, Response, request
# --- MODIFICATION START ---
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
# --- MODIFICATION END ---
import matplotlib.pyplot as plt

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

# --- MODIFICATION START ---
# Define categories to exclude from operational expense reports for consistency.
FINANCIAL_TRANSACTION_CATEGORIES = [
    'Loan Lent',         # Expense type from lending money to someone
    'Debt Repayment',    # Expense type from repaying a debt you owed
    'Loan Received',     # Income type (for completeness in exclusion lists)
    'Debt Settled',      # Income type (for completeness in exclusion lists)
    'Initial Balance'    # Adjustment type
]

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")
# --- MODIFICATION END ---

@analytics_bp.route('/report/chart', methods=['GET'])
def get_report_chart():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    try:
        # --- MODIFICATION START: Convert date strings to aware UTC range ---
        if start_date_str and end_date_str:
            start_date_local_obj = datetime.fromisoformat(start_date_str).date()
            end_date_local_obj = datetime.fromisoformat(end_date_str).date()

            # Create aware datetime objects in the local timezone
            aware_start_local = datetime.combine(start_date_local_obj, time.min, tzinfo=PHNOM_PENH_TZ)
            aware_end_local = datetime.combine(end_date_local_obj, time.max, tzinfo=PHNOM_PENH_TZ)

            # Convert to UTC for database query
            start_date_utc = aware_start_local.astimezone(UTC_TZ)
            end_date_utc = aware_end_local.astimezone(UTC_TZ)
        else:
            # Fallback for default range (less precise, consider timezone if used)
            end_date_utc = datetime.now(UTC_TZ)
            start_date_utc = end_date_utc - timedelta(days=30)
        # --- MODIFICATION END ---

    except (ValueError, TypeError):
        return Response("Invalid date format. Use YYYY-MM-DD.", status=400)

    pipeline = [
        {'$match': {
            # --- MODIFICATION START: Query using aware UTC datetimes ---
            'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc},
            # --- MODIFICATION END ---
            'type': 'expense',
            'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES}
        }},
        {'$addFields': {
            'amount_in_usd': {
                '$cond': {
                    'if': {'$eq': ['$currency', 'KHR']},
                    'then': {'$divide': ['$amount', '$exchangeRateAtTime']},
                    'else': '$amount'
                }
            }
        }},
        {'$group': {
            '_id': '$categoryId',
            'total': {'$sum': '$amount_in_usd'}
        }},
        {'$sort': {'total': -1}}
    ]

    data = list(current_app.db.transactions.aggregate(pipeline))

    if not data:
        return Response("No operational expense data found for the selected period.", status=404)

    labels = [item['_id'] for item in data]
    sizes = [item['total'] for item in data]

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')
    # Use local start date for display title for clarity
    title_start_date = datetime.fromisoformat(start_date_str).strftime('%d %b')
    title_end_date = datetime.fromisoformat(end_date_str).strftime('%d %b %Y')
    plt.title(f"Operational Expenses from {title_start_date} to {title_end_date}")

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)

    return Response(buf.getvalue(), mimetype='image/png')
# --- End of modified file: web_service/app/analytics/routes.py ---