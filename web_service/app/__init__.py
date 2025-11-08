# --- web_service/app/__init__.py (rewritten) ---

from __future__ import annotations

import io
import certifi
import requests
import matplotlib.pyplot as plt

from datetime import datetime, time, timedelta, date
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, g, current_app
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from bson import ObjectId  # noqa: F401 (kept if other modules import from here)

from .config import Config

# ----- Timezones & constants -----
PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
UTC_TZ = ZoneInfo("UTC")

FINANCIAL_TRANSACTION_CATEGORIES = [
    "Loan Lent",
    "Debt Repayment",
    "Loan Received",
    "Debt Settled",
    "Initial Balance",
]

# ----- Standard Mongo connection args (used everywhere) -----
# Keep TLS on, provide a robust CA bundle via certifi, and lengthen selection timeouts
MONGO_CONNECTION_ARGS = {
    "tls": True,
    "tlsCAFile": certifi.where(),
    # Some hosts require disabling OCSP endpoint checks in restricted egress envs
    # Keep this if your platform blocks OCSP (safe for Atlas):
    "tlsDisableOCSPEndpointCheck": True,
    "serverSelectionTimeoutMS": 30000,  # 30s for first server selection
    "connectTimeoutMS": 20000,
    "socketTimeoutMS": 20000,
}


# ---------------------------------------------------------------------------
# Utility: Telegram senders
# ---------------------------------------------------------------------------

def send_telegram_message(chat_id: str | int, text: str, token: str, parse_mode: str = "HTML") -> None:
    """Send a message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    try:
        resp = requests.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        print(f"Sent scheduled message to {chat_id}.")
    except Exception as e:  # pragma: no cover
        print(f"Failed to send scheduled message to {chat_id}: {e}")


def send_telegram_photo(chat_id: str | int, photo_bytes: bytes, token: str, caption: str = "") -> None:
    """Send a photo (bytes) via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    files = {"photo": ("report_chart.png", photo_bytes, "image/png")}
    data = {"chat_id": chat_id, "caption": caption}
    try:
        resp = requests.post(url, data=data, files=files, timeout=30)
        resp.raise_for_status()
        print(f"Sent scheduled photo to {chat_id}.")
    except Exception as e:  # pragma: no cover
        print(f"Failed to send scheduled photo to {chat_id}: {e}")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _build_client(uri: str) -> MongoClient:
    """Create a robust, singleton-friendly MongoClient with Server API v1."""
    return MongoClient(
        uri,
        server_api=ServerApi("1"),
        **MONGO_CONNECTION_ARGS,
    )


def get_db():
    """Return a per-request db handle stored on Flask's `g` context."""
    if "db_client" not in g:
        uri = current_app.config["MONGODB_URI"]
        g.db_client = _build_client(uri)
        g.db = g.db_client[current_app.config["DB_NAME"]]
    return g.db


def close_db(_e=None) -> None:
    """Close the Mongo client when the app context tears down."""
    client = g.pop("db_client", None)
    if client is not None:
        client.close()
        g.pop("db", None)
        print("MongoDB connection closed for this context.")


# ---------------------------------------------------------------------------
# Report/Analytics helpers
# ---------------------------------------------------------------------------

def _pp_range(start_local: date, end_local: date) -> tuple[datetime, datetime]:
    """Convert local date range to UTC datetimes inclusive."""
    aware_start_local = datetime.combine(start_local, time.min, tzinfo=PHNOM_PENH_TZ)
    aware_end_local = datetime.combine(end_local, time.max, tzinfo=PHNOM_PENH_TZ)
    return aware_start_local.astimezone(UTC_TZ), aware_end_local.astimezone(UTC_TZ)


def get_report_data(start_date_local: date, end_date_local: date, db) -> dict:
    """Compute a summarized report for the given period."""
    start_utc, end_utc = _pp_range(start_date_local, end_date_local)

    add_fields_stage = {
        "$addFields": {
            "amount_in_usd": {
                "$cond": {
                    "if": {"$eq": ["$currency", "USD"]},
                    "then": "$amount",
                    "else": {
                        "$let": {
                            "vars": {"rate": {"$ifNull": ["$exchangeRateAtTime", 4100.0]}},
                            "in": {
                                "$cond": {
                                    "if": {"$gt": ["$$rate", 0]},
                                    "then": {"$divide": ["$amount", "$$rate"]},
                                    "else": {"$divide": ["$amount", 4100.0]},
                                }
                            },
                        }
                    },
                }
            }
        }
    }

    # Balance at start
    start_balance_pipeline = [
        {"$match": {"timestamp": {"$lt": start_utc}}},
        add_fields_stage,
        {"$group": {"_id": "$type", "totalUSD": {"$sum": "$amount_in_usd"}}},
    ]
    start_balance_data = list(db.transactions.aggregate(start_balance_pipeline))
    start_income = next((d["totalUSD"] for d in start_balance_data if d["_id"] == "income"), 0)
    start_expense = next((d["totalUSD"] for d in start_balance_data if d["_id"] == "expense"), 0)
    balance_at_start_usd = start_income - start_expense

    # Operational window (exclude financial-only categories)
    operational_pipeline = [
        {
            "$match": {
                "timestamp": {"$gte": start_utc, "$lte": end_utc},
                "categoryId": {"$nin": FINANCIAL_TRANSACTION_CATEGORIES},
            }
        },
        add_fields_stage,
        {"$group": {"_id": {"type": "$type", "category": "$categoryId"}, "total": {"$sum": "$amount_in_usd"}}},
        {"$sort": {"total": -1}},
    ]
    operational = list(db.transactions.aggregate(operational_pipeline))

    report = {
        "startDate": start_date_local.isoformat(),
        "endDate": end_date_local.isoformat(),
        "summary": {
            "totalIncomeUSD": 0.0,
            "totalExpenseUSD": 0.0,
            "netSavingsUSD": 0.0,
            "balanceAtStartUSD": float(balance_at_start_usd),
        },
        "expenseBreakdown": [],
    }

    for item in operational:
        t = item["_id"]["type"]
        if t == "income":
            report["summary"]["totalIncomeUSD"] += float(item["total"])
        elif t == "expense":
            report["summary"]["totalExpenseUSD"] += float(item["total"])
            report["expenseBreakdown"].append({
                "category": item["_id"]["category"],
                "totalUSD": float(item["total"]),
            })

    report["summary"]["netSavingsUSD"] = (
            report["summary"]["totalIncomeUSD"] - report["summary"]["totalExpenseUSD"]
    )
    return report


def format_scheduled_report_message(data: dict) -> str:
    summary = data.get("summary", {})
    start_date = datetime.fromisoformat(data["startDate"]).strftime("%b %d, %Y")
    end_date = datetime.fromisoformat(data["endDate"]).strftime("%b %d, %Y")

    header = f"🗓️ <b>Scheduled Financial Report</b>\n<i>{start_date} to {end_date}</i>\n\n"
    income = summary.get("totalIncomeUSD", 0.0)
    expense = summary.get("totalExpenseUSD", 0.0)
    net = summary.get("netSavingsUSD", 0.0)

    summary_text = (
        f"<b>Summary (in USD):</b>\n"
        f"⬆️ Income: ${income:,.2f}\n"
        f"⬇️ Expense: ${expense:,.2f}\n"
        f"<b>Net: ${net:,.2f}</b> {'✅' if net >= 0 else '🔻'}\n\n"
    )

    expense_breakdown = data.get("expenseBreakdown", [])
    expense_text = "<b>Top Expenses:</b>\n"
    if expense_breakdown:
        for item in expense_breakdown[:3]:
            expense_text += f"    - {item['category']}: ${item['totalUSD']:,.2f}\n"
    else:
        expense_text += "    - No expenses recorded.\n"
    return header + summary_text + expense_text


def create_pie_chart_from_data(data: dict, start_date: date, end_date: date) -> bytes | None:
    expense_breakdown = data.get("expenseBreakdown", [])
    total_expense = float(data.get("summary", {}).get("totalExpenseUSD", 0))
    if not expense_breakdown or total_expense == 0:
        return None

    # Roll up categories contributing < 4% into "Other"
    threshold_pct = 4.0
    labels: list[str] = []
    sizes: list[float] = []
    other_total = 0.0

    for item in expense_breakdown:
        pct = (float(item["totalUSD"]) / total_expense) * 100
        if pct < threshold_pct:
            other_total += float(item["totalUSD"])
        else:
            labels.append(item["category"])
            sizes.append(float(item["totalUSD"]))
    if other_total > 0:
        labels.append("Other")
        sizes.append(other_total)

    date_range_str = f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}"

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.set_title("Expense Breakdown", pad=20)
    plt.suptitle(date_range_str, y=0.93, fontsize=10)
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
    ax.axis("equal")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------

def _send_report_job(period_name: str, start_date: date, end_date: date, db, token: str, chat_id: str | int) -> None:
    data = get_report_data(start_date, end_date, db)
    if data and data.get("summary", {}).get("totalExpenseUSD", 0) > 0:
        msg = format_scheduled_report_message(data)
        send_telegram_message(chat_id, msg, token)
        pie = create_pie_chart_from_data(data, start_date, end_date)
        if pie:
            send_telegram_photo(chat_id, pie, token)
    else:
        msg = (
            f"📊 No significant activity recorded for the {period_name} "
            f"({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})."
        )
        send_telegram_message(chat_id, msg, token)


def run_scheduled_report(period: str) -> None:
    """Entry point used by APScheduler to generate scheduled reports."""
    print(f"Running {period} scheduled report job…")

    client = _build_client(Config.MONGODB_URI)
    db = client[Config.DB_NAME]
    token = Config.TELEGRAM_TOKEN

    # NOTE: user-specific reporting planned; currently falls back to global chat
    chat_id = Config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        print(f"Skipping {period} report: Telegram token or chat ID not configured.")
        client.close()
        return

    today = datetime.now(PHNOM_PENH_TZ).date()

    if period == "weekly":
        # previous full week Mon–Sun
        end_date = today - timedelta(days=today.weekday() + 1)
        start_date = end_date - timedelta(days=6)
        _send_report_job("previous week", start_date, end_date, db, token, chat_id)

    elif period == "monthly":
        end_date = (today.replace(day=1) - timedelta(days=1))  # last day of prior month
        start_date = end_date.replace(day=1)
        _send_report_job("previous month", start_date, end_date, db, token, chat_id)

    elif period == "semesterly":
        if today.month == 1:  # January → report Jul–Dec of previous year
            end_date = today.replace(year=today.year - 1, month=12, day=31)
            start_date = today.replace(year=today.year - 1, month=7, day=1)
            _send_report_job("last semester", start_date, end_date, db, token, chat_id)
        elif today.month == 7:  # July → report Jan–Jun same year
            end_date = today.replace(month=6, day=30)
            start_date = today.replace(month=1, day=1)
            _send_report_job("first semester", start_date, end_date, db, token, chat_id)

    elif period == "yearly":
        end_date = today.replace(year=today.year - 1, month=12, day=31)
        start_date = today.replace(year=today.year - 1, month=1, day=1)
        _send_report_job("previous year", start_date, end_date, db, token, chat_id)

    client.close()
    print(f"{period.capitalize()} report job finished.")


def send_daily_reminder_job() -> None:
    """Daily reminder job (currently global, not per-user)."""
    client = _build_client(Config.MONGODB_URI)
    db = client[Config.DB_NAME]

    token = Config.TELEGRAM_TOKEN
    chat_id = Config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        print("Skipped daily transaction reminder, config missing.")
        client.close()
        return

    now_local = datetime.now(PHNOM_PENH_TZ)
    today_start_local = datetime.combine(now_local.date(), time.min, tzinfo=PHNOM_PENH_TZ)
    today_start_utc = today_start_local.astimezone(UTC_TZ)

    count = db.transactions.count_documents({"timestamp": {"$gte": today_start_utc}})

    if count == 0:
        message = (
            "Hey! 잊지마! (Don't forget!)\n\n"
            "Looks like you haven't logged any transactions today. "
            "Take a moment to log your activity! ✍️"
        )
        send_telegram_message(chat_id, message, token, parse_mode="Markdown")
        print("Sent daily transaction reminder.")
    else:
        print("Skipped daily transaction reminder, transactions found.")

    client.close()


# ---------------------------------------------------------------------------
# Flask app factory
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Make sure critical config is explicitly present on the app
    app.config["MONGODB_URI"] = Config.MONGODB_URI
    app.config["DB_NAME"] = Config.DB_NAME
    app.config["TELEGRAM_TOKEN"] = Config.TELEGRAM_TOKEN

    # Close per-request clients on teardown
    app.teardown_appcontext(close_db)

    # Scheduler (Asia/Phnom_Penh)
    scheduler = BackgroundScheduler(daemon=True, timezone="Asia/Phnom_Penh")
    scheduler.add_job(
        send_daily_reminder_job,
        trigger=CronTrigger(hour=21, minute=0),
        id="daily_reminder",
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_report,
        args=["weekly"],
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="weekly_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_report,
        args=["monthly"],
        trigger=CronTrigger(day=1, hour=8, minute=30),
        id="monthly_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_report,
        args=["semesterly"],
        trigger=CronTrigger(month="1,7", day=1, hour=9, minute=0),
        id="semesterly_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_report,
        args=["yearly"],
        trigger=CronTrigger(month=1, day=1, hour=9, minute=30),
        id="yearly_report",
        replace_existing=True,
    )

    scheduler.start()
    app.scheduler = scheduler
    print("⏰ Scheduler started with daily, weekly, monthly, semesterly, and yearly jobs.")

    # Register blueprints
    from .settings.routes import settings_bp
    from .analytics.routes import analytics_bp
    from .transactions.routes import transactions_bp
    from .debts.routes import debts_bp
    from .summary.routes import summary_bp
    from .reminders.routes import reminders_bp
    from .auth.routes import auth_bp

    app.register_blueprint(settings_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(debts_bp)
    app.register_blueprint(summary_bp)
    app.register_blueprint(reminders_bp)
    app.register_blueprint(auth_bp)

    @app.route("/health")
    def health_check():
        return jsonify({"status": "ok"})

    return app
