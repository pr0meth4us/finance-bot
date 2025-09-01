import io
from flask import Blueprint, current_app, Response, request
from datetime import datetime, timedelta, time
import matplotlib.pyplot as plt

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


@analytics_bp.route('/report/chart', methods=['GET'])
def get_report_chart():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    try:
        if start_date_str and end_date_str:
            start_date = datetime.fromisoformat(start_date_str)
            end_date = datetime.fromisoformat(end_date_str)
            end_date = datetime.combine(end_date.date(), time.max)
        else:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)
    except (ValueError, TypeError):
        return Response("Invalid date format. Use YYYY-MM-DD.", status=400)

    pipeline = [
        {'$match': {
            'timestamp': {'$gte': start_date, '$lte': end_date},
            'type': 'expense'
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
        return Response("No expense data for the selected period.", status=404)

    labels = [item['_id'] for item in data]
    sizes = [item['total'] for item in data]

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')
    title = f"Expenses from {start_date.strftime('%d %b')} to {end_date.strftime('%d %b %Y')}"
    plt.title(title)

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)

    return Response(buf.getvalue(), mimetype='image/png')