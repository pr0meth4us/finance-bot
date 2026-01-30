# web_service/app/services/scheduler.py

import certifi
from pymongo import MongoClient
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from ..config import Config
from ..utils.telegram_helpers import send_telegram_message, send_telegram_photo
from .reporting import get_report_data, format_scheduled_report_message, create_pie_chart_from_data

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")

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