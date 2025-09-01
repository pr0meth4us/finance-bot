import io
from flask import Blueprint, current_app, Response
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

@analytics_bp.route('/report/chart', methods=['GET'])
def get_report_chart():
    settings = current_app.db.settings.find_one({'_id': 'config'})
    khr_rate = settings.get('khr_to_usd_rate', 4100) if settings else 4100

    start_date = datetime.utcnow() - timedelta(days=30)

    pipeline = [
        {'$match': {'timestamp': {'$gte': start_date}, 'type': 'expense'}},
        {'$addFields': {
            'amount_in_usd': {
                '$cond': {
                    'if': {'$eq': ['$currency', 'KHR']},
                    'then': {'$divide': ['$amount', khr_rate]},
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
        return Response("No expense data for the period.", status=404)

    labels = [item['_id'] for item in data]
    sizes = [item['total'] for item in data]

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')
    plt.title(f"Expenses (Last 30 Days, in USD)\nRate: 1 USD = {khr_rate} KHR")

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)

    return Response(buf.getvalue(), mimetype='image/png')