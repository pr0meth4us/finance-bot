import io
import logging
import requests
import matplotlib.pyplot as plt
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from pymongo import MongoClient
from app.config import Config
from app.utils.db import MONGO_CONNECTION_ARGS
from app.utils.currency import get_live_usd_to_khr_rate

log = logging.getLogger(__name__)
PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")


# Reuse pipeline logic for consistency, albeit simplified for reports
# Note: We reconstruct some logic here to avoid circular imports or context issues
# when running outside request context.

def send_telegram_message(chat_id, text, token, parse_mode='HTML'):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
    except Exception as e:
        log.warning(f"Failed to send message to {chat_id}: {e}")


def send_telegram_photo(chat_id, photo_bytes, token, caption=""):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    files = {'photo': ('report_chart.png', photo_bytes, 'image/png')}
    data = {'chat_id': chat_id, 'caption': caption}
    try:
        response = requests.post(url, data=data, files=files, timeout=30)
        response.raise_for_status()
    except Exception as e:
        log.warning(f"Failed to send photo to {chat_id}: {e}")


def _get_user_specific_report_data(start_date_local, end_date_local, db, user_settings_doc):
    """
    Generates report data for a specific user context.
    """
    # Import pipelines dynamically to avoid circular imports with app context if any
    from app.analytics.pipelines import (
        build_start_balance_pipeline,
        build_operational_pipeline,
        build_top_expense_pipeline
    )

    account_id = user_settings_doc['account_id']
    settings = user_settings_doc.get('settings', {})

    # Rate logic
    rate_pref = settings.get('rate_preference', 'live')
    user_rate = settings.get('fixed_rate', 4100.0) if rate_pref == 'fixed' else get_live_usd_to_khr_rate()

    # Initial Balances
    initial = settings.get('initial_balances', {})
    initial_usd = initial.get('USD', 0) + (initial.get('KHR', 0) / user_rate)

    # Dates
    aware_start = datetime.combine(start_date_local, time.min, tzinfo=PHNOM_PENH_TZ)
    aware_end = datetime.combine(end_date_local, time.max, tzinfo=PHNOM_PENH_TZ)
    start_utc = aware_start.astimezone(UTC_TZ)
    end_utc = aware_end.astimezone(UTC_TZ)

    user_match = {'account_id': account_id}
    date_range_match = {'timestamp': {'$gte': start_utc, '$lte': end_utc}}

    # Balance Calculation
    start_bal_data = list(db.transactions.aggregate(build_start_balance_pipeline(start_utc, user_match, user_rate)))
    start_inc = next((i['totalUSD'] for i in start_bal_data if i['_id'] == 'income'), 0)
    start_exp = next((i['totalUSD'] for i in start_bal_data if i['_id'] == 'expense'), 0)
    balance_start = initial_usd + start_inc - start_exp

    # Operational Data
    op_data = list(db.transactions.aggregate(build_operational_pipeline(date_range_match, user_match, user_rate)))

    report = {
        "startDate": start_date_local.isoformat(),
        "endDate": end_date_local.isoformat(),
        "summary": {"totalIncomeUSD": 0, "totalExpenseUSD": 0, "netSavingsUSD": 0, "balanceAtStartUSD": balance_start},
        "expenseBreakdown": []
    }

    for item in op_data:
        if item['_id']['type'] == 'income':
            report['summary']['totalIncomeUSD'] += item['total']
        elif item['_id']['type'] == 'expense':
            report['summary']['totalExpenseUSD'] += item['total']
            report['expenseBreakdown'].append({'category': item['_id']['category'], 'totalUSD': item['total']})

    report['summary']['netSavingsUSD'] = report['summary']['totalIncomeUSD'] - report['summary']['totalExpenseUSD']
    return report


def _format_message(data):
    s = data['summary']
    start = datetime.fromisoformat(data['startDate']).strftime('%b %d')
    end = datetime.fromisoformat(data['endDate']).strftime('%b %d')

    msg = (f"🗓️ <b>Report: {start} - {end}</b>\n\n"
           f"⬆️ Income: ${s['totalIncomeUSD']:,.2f}\n"
           f"⬇️ Expense: ${s['totalExpenseUSD']:,.2f}\n"
           f"<b>Net: ${s['netSavingsUSD']:,.2f}</b>\n\n"
           f"<b>Top Expenses:</b>\n")

    if data['expenseBreakdown']:
        for item in data['expenseBreakdown'][:3]:
            msg += f"  - {item['category']}: ${item['totalUSD']:,.2f}\n"
    else:
        msg += "  - No expenses.\n"
    return msg


def _create_chart(data, start_date, end_date):
    breakdown = data.get('expenseBreakdown', [])
    total = data['summary']['totalExpenseUSD']
    if not breakdown or total == 0:
        return None

    labels, sizes, other = [], [], 0
    for item in breakdown:
        if (item['totalUSD'] / total) * 100 < 4.0:
            other += item['totalUSD']
        else:
            labels.append(item['category'])
            sizes.append(item['totalUSD'])

    if other > 0:
        labels.append('Other')
        sizes.append(other)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.set_title(f"Expenses: {start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}")
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def run_scheduled_report(period):
    try:
        client = MongoClient(Config.MONGODB_URI, **MONGO_CONNECTION_ARGS)
        db = client[Config.DB_NAME]
        token = Config.TELEGRAM_TOKEN
    except Exception as e:
        log.error(f"Scheduled job DB connection failed: {e}")
        return

    try:
        users = list(db.settings.find({"settings.notification_chat_ids.report": {"$ne": None}}))
    except Exception as e:
        log.error(f"Failed to fetch users for report: {e}")
        client.close()
        return

    today = datetime.now(PHNOM_PENH_TZ).date()
    start_date, end_date = None, None

    if period == 'weekly':
        end_date = today - timedelta(days=today.weekday() + 1)
        start_date = end_date - timedelta(days=6)
    elif period == 'monthly':
        end_date = today.replace(day=1) - timedelta(days=1)
        start_date = end_date.replace(day=1)
    # (Simpler implementation: Only implementing weekly/monthly for brevity, extend as needed)

    if not start_date or not end_date:
        client.close()
        return

    for user in users:
        try:
            chat_id = user['settings']['notification_chat_ids']['report']
            data = _get_user_specific_report_data(start_date, end_date, db, user)
            if data['summary']['totalExpenseUSD'] > 0 or data['summary']['totalIncomeUSD'] > 0:
                send_telegram_message(chat_id, _format_message(data), token)
                chart = _create_chart(data, start_date, end_date)
                if chart:
                    send_telegram_photo(chat_id, chart, token)
        except Exception as e:
            log.error(f"Report failed for user {user.get('account_id')}: {e}")

    client.close()


def send_daily_reminder_job():
    try:
        client = MongoClient(Config.MONGODB_URI, **MONGO_CONNECTION_ARGS)
        db = client[Config.DB_NAME]
        token = Config.TELEGRAM_TOKEN
    except Exception:
        return

    now = datetime.now(PHNOM_PENH_TZ)
    today_utc = datetime.combine(now.date(), time.min, tzinfo=PHNOM_PENH_TZ).astimezone(UTC_TZ)

    users = list(db.settings.find({"settings.notification_chat_ids.reminder": {"$ne": None}}))
    for user in users:
        try:
            uid = user['account_id']
            if db.transactions.count_documents({'timestamp': {'$gte': today_utc}, 'account_id': uid}) == 0:
                chat_id = user['settings']['notification_chat_ids']['reminder']
                lang = user.get('settings', {}).get('language', 'en')
                msg = "សួស្តី!\nកុំភ្លេចកត់ត្រាចំណាយថ្ងៃនេះណា! ✍️" if lang == 'km' else "Hey!\nDon't forget to log your transactions today! ✍️"
                send_telegram_message(chat_id, msg, token, parse_mode='Markdown')
        except Exception as e:
            log.error(f"Reminder failed for user {user.get('account_id')}: {e}")

    client.close()