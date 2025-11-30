import certifi
import io
import requests
import matplotlib.pyplot as plt
from flask import Flask, jsonify, current_app
from flask_cors import CORS
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .config import Config
from datetime import datetime, time, timedelta, date
from zoneinfo import ZoneInfo
from bson import ObjectId

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")

FINANCIAL_TRANSACTION_CATEGORIES = [
    'Loan Lent', 'Debt Repayment', 'Loan Received', 'Debt Settled', 'Initial Balance'
]


# ---------------------------------------------------------------------
# DB HELPER
# ---------------------------------------------------------------------
def get_db(app=None):
    """
    Helper to get MongoDB database instance.
    - In request context: use current_app.db
    - Outside: you can pass an app explicitly.
    """
    if app is not None:
        return app.db
    return current_app.db


# ---------------------------------------------------------------------
# TELEGRAM HELPERS
# ---------------------------------------------------------------------
def send_telegram_message(chat_id, text, token, parse_mode='HTML'):
    """A simple function to send a message via the Telegram API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        print(f"Sent scheduled message to {chat_id}.")
    except Exception as e:
        print(f"Failed to send scheduled message to {chat_id}: {e}")


def send_telegram_photo(chat_id, photo_bytes, token, caption=""):
    """Sends a photo from bytes via the Telegram API."""
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    files = {'photo': ('report_chart.png', photo_bytes, 'image/png')}
    data = {'chat_id': chat_id, 'caption': caption}
    try:
        response = requests.post(url, data=data, files=files, timeout=30)
        response.raise_for_status()
        print(f"Sent scheduled photo to {chat_id}.")
    except Exception as e:
        print(f"Failed to send scheduled photo to {chat_id}: {e}")


# ---------------------------------------------------------------------
# REPORT LOGIC
# ---------------------------------------------------------------------
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


# ---------------------------------------------------------------------
# SCHEDULED JOBS
# ---------------------------------------------------------------------
def _send_report_job(period_name, start_date, end_date, db, token, chat_id):
    """Generic helper to generate and send a report."""
    report_data = get_report_data(start_date, end_date, db)
    if report_data and report_data.get('summary', {}).get('totalExpenseUSD', 0) > 0:
        message = format_scheduled_report_message(report_data)
        send_telegram_message(chat_id, message, token)
        pie_chart_bytes = create_pie_chart_from_data(report_data, start_date, end_date)
        if pie_chart_bytes:
            send_telegram_photo(chat_id, pie_chart_bytes, token)
    else:
        message = (
            f"📊 No significant activity recorded for the {period_name} "
            f"({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})."
        )
        send_telegram_message(chat_id, message, token)


def run_scheduled_report(period):
    """Main function called by scheduler to run a report for a given period."""
    print(f"Running {period} scheduled report job...")
    client = MongoClient(Config.MONGODB_URI, tls=True, tlsCAFile=certifi.where())
    db = client[Config.DB_NAME]
    token = Config.TELEGRAM_TOKEN
    chat_id = Config.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        print(f"Skipping {period} report: Telegram token or chat ID not configured.")
        client.close()
        return

    today = datetime.now(PHNOM_PENH_TZ).date()

    if period == 'weekly':
        end_date = today - timedelta(days=today.weekday() + 1)
        start_date = end_date - timedelta(days=6)
        _send_report_job('previous week', start_date, end_date, db, token, chat_id)
    elif period == 'monthly':
        end_date = today.replace(day=1) - timedelta(days=1)
        start_date = end_date.replace(day=1)
        _send_report_job('previous month', start_date, end_date, db, token, chat_id)
    elif period == 'semesterly':
        if today.month == 1:  # January → Jul–Dec of last year
            end_date = today.replace(year=today.year - 1, month=12, day=31)
            start_date = today.replace(year=today.year - 1, month=7, day=1)
            _send_report_job('last semester', start_date, end_date, db, token, chat_id)
        elif today.month == 7:  # July → Jan–Jun of this year
            end_date = today.replace(month=6, day=30)
            start_date = today.replace(month=1, day=1)
            _send_report_job('first semester', start_date, end_date, db, token, chat_id)
    elif period == 'yearly':
        end_date = today.replace(year=today.year - 1, month=12, day=31)
        start_date = today.replace(year=today.year - 1, month=1, day=1)
        _send_report_job('previous year', start_date, end_date, db, token, chat_id)

    client.close()
    print(f"{period.capitalize()} report job finished.")


def send_daily_reminder_job():
    client = MongoClient(Config.MONGODB_URI, tls=True, tlsCAFile=certifi.where())
    db = client[Config.DB_NAME]
    now_in_phnom_penh = datetime.now(PHNOM_PENH_TZ)
    today_start_local_aware = datetime.combine(now_in_phnom_penh.date(), time.min, tzinfo=PHNOM_PENH_TZ)
    today_start_utc = today_start_local_aware.astimezone(UTC_TZ)

    count = db.transactions.count_documents({'timestamp': {'$gte': today_start_utc}})
    if count == 0 and Config.TELEGRAM_TOKEN and Config.TELEGRAM_CHAT_ID:
        token, chat_id = Config.TELEGRAM_TOKEN, Config.TELEGRAM_CHAT_ID
        message = (
            "Hey! 잊지마! (Don't forget!)\n\n"
            "Looks like you haven't logged any transactions today. "
            "Take a moment to log your activity! ✍️"
        )
        send_telegram_message(chat_id, message, token, parse_mode='Markdown')
        print("Sent daily transaction reminder.")
    else:
        print("Skipped daily transaction reminder, transactions found or config missing.")

    client.close()


# ---------------------------------------------------------------------
# APP FACTORY
# ---------------------------------------------------------------------
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # --- CORS CONFIG (fixed) ---
    CORS(app, resources={
        r"/*": {
            "origins": [
                "https://savvify-web.vercel.app",
                "http://localhost:3000"
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    client = MongoClient(Config.MONGODB_URI, tls=True, tlsCAFile=certifi.where())
    app.db = client[Config.DB_NAME]
    print("✅ MongoDB connection successful.")

    scheduler = BackgroundScheduler(daemon=True, timezone='Asia/Phnom_Penh')

    scheduler.add_job(
        send_daily_reminder_job,
        trigger=CronTrigger(hour=21, minute=0),
        id='daily_reminder',
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_report,
        args=['weekly'],
        trigger=CronTrigger(day_of_week='mon', hour=8, minute=0),
        id='weekly_report',
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_report,
        args=['monthly'],
        trigger=CronTrigger(day=1, hour=8, minute=30),
        id='monthly_report',
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_report,
        args=['semesterly'],
        trigger=CronTrigger(month='1,7', day=1, hour=9, minute=0),
        id='semesterly_report',
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_report,
        args=['yearly'],
        trigger=CronTrigger(month=1, day=1, hour=9, minute=30),
        id='yearly_report',
        replace_existing=True,
    )

    scheduler.start()
    app.scheduler = scheduler
    print("⏰ Scheduler started with daily, weekly, monthly, semesterly, and yearly jobs.")

    # Register Blueprints
    from .settings.routes import settings_bp
    from .analytics.routes import analytics_bp
    from .transactions.routes import transactions_bp
    from .debts.routes import debts_bp
    from .summary.routes import summary_bp
    from .reminders.routes import reminders_bp
    from .auth.routes import auth_bp
    from .users.routes import users_bp

    app.register_blueprint(settings_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(debts_bp)
    app.register_blueprint(summary_bp)
    app.register_blueprint(reminders_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)

    @app.route("/health")
    def health_check():
        return jsonify({"status": "ok"})

    return app
