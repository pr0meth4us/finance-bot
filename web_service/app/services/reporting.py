# web_service/app/services/reporting.py

import io
import matplotlib.pyplot as plt
from datetime import datetime, time
from zoneinfo import ZoneInfo

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")

FINANCIAL_TRANSACTION_CATEGORIES = [
    'Loan Lent', 'Debt Repayment', 'Loan Received', 'Debt Settled', 'Initial Balance'
]

def get_report_data(start_date_local_obj, end_date_local_obj, db):
    """Internal logic to fetch detailed report data."""
    aware_start_local = datetime.combine(start_date_local_obj, time.min, tzinfo=PHNOM_PENH_TZ)
    aware_end_local = datetime.combine(end_date_local_obj, time.max, tzinfo=PHNOM_PENH_TZ)
    start_date_utc = aware_start_local.astimezone(UTC_TZ)
    end_date_utc = aware_end_local.astimezone(UTC_TZ)

    add_fields_stage = {
        '$addFields': {
            'amount_in_usd': {
                '$cond': {
                    'if': {'$eq': ['$currency', 'USD']},
                    'then': '$amount',
                    'else': {
                        '$let': {
                            'vars': {'rate': {'$ifNull': ['$exchangeRateAtTime', 4100.0]}},
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

    start_balance_pipeline = [
        {'$match': {'timestamp': {'$lt': start_date_utc}}},
        add_fields_stage,
        {'$group': {'_id': '$type', 'totalUSD': {'$sum': '$amount_in_usd'}}}
    ]
    start_balance_data = list(db.transactions.aggregate(start_balance_pipeline))
    start_income = next((item['totalUSD'] for item in start_balance_data if item['_id'] == 'income'), 0)
    start_expense = next((item['totalUSD'] for item in start_balance_data if item['_id'] == 'expense'), 0)
    balance_at_start_usd = start_income - start_expense

    operational_pipeline = [
        {
            '$match': {
                'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc},
                'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES}
            }
        },
        add_fields_stage,
        {
            '$group': {
                '_id': {'type': '$type', 'category': '$categoryId'},
                'total': {'$sum': '$amount_in_usd'}
            }
        },
        {'$sort': {'total': -1}}
    ]
    operational_data = list(db.transactions.aggregate(operational_pipeline))

    report = {
        "startDate": start_date_local_obj.isoformat(),
        "endDate": end_date_local_obj.isoformat(),
        "summary": {
            "totalIncomeUSD": 0,
            "totalExpenseUSD": 0,
            "netSavingsUSD": 0,
            "balanceAtStartUSD": balance_at_start_usd
        },
        "expenseBreakdown": []
    }

    for item in operational_data:
        if item['_id']['type'] == 'income':
            report['summary']['totalIncomeUSD'] += item['total']
        elif item['_id']['type'] == 'expense':
            report['summary']['totalExpenseUSD'] += item['total']
            report['expenseBreakdown'].append({
                'category': item['_id']['category'],
                'totalUSD': item['total']
            })

    report['summary']['netSavingsUSD'] = (
            report['summary']['totalIncomeUSD'] - report['summary']['totalExpenseUSD']
    )
    return report


def format_scheduled_report_message(data):
    summary = data.get('summary', {})
    start_date = datetime.fromisoformat(data['startDate']).strftime('%b %d, %Y')
    end_date = datetime.fromisoformat(data['endDate']).strftime('%b %d, %Y')

    header = f"🗓️ <b>Scheduled Financial Report</b>\n<i>{start_date} to {end_date}</i>\n\n"
    income = summary.get('totalIncomeUSD', 0)
    expense = summary.get('totalExpenseUSD', 0)
    net = summary.get('netSavingsUSD', 0)

    summary_text = (
        f"<b>Summary (in USD):</b>\n"
        f"⬆️ Income: ${income:,.2f}\n"
        f"⬇️ Expense: ${expense:,.2f}\n"
        f"<b>Net: ${net:,.2f}</b> {'✅' if net >= 0 else '🔻'}\n\n"
    )

    expense_breakdown = data.get('expenseBreakdown', [])
    expense_text = "<b>Top Expenses:</b>\n"
    if expense_breakdown:
        for item in expense_breakdown[:3]:
            expense_text += f"    - {item['category']}: ${item['totalUSD']:,.2f}\n"
    else:
        expense_text += "    - No expenses recorded.\n"

    return header + summary_text + expense_text


def create_pie_chart_from_data(data, start_date, end_date):
    expense_breakdown = data.get('expenseBreakdown', [])
    total_expense = data.get('summary', {}).get('totalExpenseUSD', 0)
    if not expense_breakdown or total_expense == 0:
        return None

    threshold = 4.0
    new_labels, new_sizes, other_total = [], [], 0

    for item in expense_breakdown:
        percentage = (item['totalUSD'] / total_expense) * 100
        if percentage < threshold:
            other_total += item['totalUSD']
        else:
            new_labels.append(item['category'])
            new_sizes.append(item['totalUSD'])

    if other_total > 0:
        new_labels.append('Other')
        new_sizes.append(other_total)

    labels, sizes = new_labels, new_sizes
    date_range_str = f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}"

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.set_title('Expense Breakdown', pad=20)
    plt.suptitle(date_range_str, y=0.93, fontsize=10)
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()