# --- Start of file: telegram_bot/handlers/analytics.py ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import keyboards
import api_client
from decorators import restricted
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from .helpers import (
    _format_report_summary_message,
    _create_income_expense_chart,
    _create_expense_pie_chart,
    _format_habits_message,
    _create_spending_line_chart
)

# Conversation states
(
    CHOOSE_REPORT_PERIOD, REPORT_ASK_START_DATE, REPORT_ASK_END_DATE,
    CHOOSE_HABITS_PERIOD
) = range(4)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")

# --- FIX: Define REGEX for this handler ---
REPORT_PERIOD_REGEX = '^(Today|This Week|Last Week|This Month|Last Month|Custom Range)$'


# --- Report Generation ---
@restricted
async def report_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the menu for selecting a report period."""
    await update.message.reply_text(
        "What period would you like a report for?",
        reply_markup=keyboards.report_period_keyboard()
    )
    return CHOOSE_REPORT_PERIOD


@restricted
async def process_report_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles standard period selection or transitions to custom date entry."""
    period_text = update.message.text

    period_map = {
        "Today": "today",
        "This Week": "this_week",
        "Last Week": "last_week",
        "This Month": "this_month",
        "Last Month": "last_month",
        "Custom Range": "custom"
    }

    period = period_map.get(period_text)
    if not period:
        await update.message.reply_text("Invalid choice. Please select from the keyboard.", reply_markup=keyboards.report_period_keyboard())
        return CHOOSE_REPORT_PERIOD

    if period == "custom":
        await update.message.reply_text("Please enter the start date (YYYY-MM-DD):", reply_markup=keyboards.HIDE_KEYBOARD)
        return REPORT_ASK_START_DATE

    today = datetime.now(PHNOM_PENH_TZ).date()
    end_of_last_month = today.replace(day=1) - timedelta(days=1)
    start_of_last_month = end_of_last_month.replace(day=1)
    date_ranges = {
        "today": (today, today),
        "this_week": (today - timedelta(days=today.weekday()),
                      today - timedelta(days=today.weekday()) + timedelta(days=6)),
        "last_week": (today - timedelta(days=today.weekday() + 7), today - timedelta(days=today.weekday() + 1)),
        "this_month": (today.replace(day=1),
                       (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)),
        "last_month": (start_of_last_month, end_of_last_month)
    }

    date_pair = date_ranges.get(period)
    if date_pair:
        start_date, end_date = date_pair
        await _generate_report(update, context, start_date, end_date)
    else:
        await update.message.reply_text("Invalid period selected.", reply_markup=keyboards.main_menu_keyboard())

    return ConversationHandler.END


@restricted
async def received_report_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and validates the custom start date."""
    try:
        start_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['report_start_date'] = start_date
        await update.message.reply_text(
            f"Start date set to {start_date:%Y-%m-%d}.\nNow, please enter the end date (YYYY-MM-DD):")
        return REPORT_ASK_END_DATE
    except ValueError:
        await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD.")
        return REPORT_ASK_START_DATE


@restricted
async def received_report_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives, validates end date, and generates the report."""
    try:
        end_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        start_date = context.user_data.get('report_start_date')
        if not start_date or end_date < start_date:
            await update.message.reply_text("Invalid date range. End date cannot be before start date.")
            return REPORT_ASK_END_DATE
        await _generate_report(update, context, start_date, end_date)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD.")
        return REPORT_ASK_END_DATE
    finally:
        context.user_data.pop('report_start_date', None)


async def _generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE, start_date, end_date):
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    """Shared logic to generate and send report summary and charts."""
    chat_id = update.effective_chat.id
    loading_text = f"📈 Generating your report for {start_date:%b %d, %Y} to {end_date:%b %d, %Y}..."
    # Send main keyboard to replace any conversation keyboards
    loading_message = await context.bot.send_message(chat_id=chat_id, text=loading_text, reply_markup=keyboards.main_menu_keyboard())

    report_data = api_client.get_detailed_report(start_date, end_date)
    await loading_message.delete()

    if report_data:
        summary_message = _format_report_summary_message(report_data)
        await context.bot.send_message(chat_id=chat_id, text=summary_message, parse_mode='HTML')

        if bar_chart := _create_income_expense_chart(report_data, start_date, end_date):
            await context.bot.send_photo(chat_id=chat_id, photo=bar_chart)

        if line_chart := _create_spending_line_chart(report_data, start_date, end_date):
            await context.bot.send_photo(chat_id=chat_id, photo=line_chart)

        if pie_chart := _create_expense_pie_chart(report_data, start_date, end_date):
            await context.bot.send_photo(chat_id=chat_id, photo=pie_chart)

        await context.bot.send_message(chat_id=chat_id, text="Report complete! What's next?",
                                       reply_markup=keyboards.main_menu_keyboard())
    else:
        await context.bot.send_message(chat_id=chat_id,
                                       text="Could not generate report. No data found for this period.",
                                       reply_markup=keyboards.main_menu_keyboard())


# --- Habits Analysis ---
@restricted
async def habits_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays menu to choose a period for habits analysis."""
    await update.message.reply_text(
        "🧠 For which period would you like to analyze your spending habits?",
        reply_markup=keyboards.report_period_keyboard()
    )
    return CHOOSE_HABITS_PERIOD


async def process_habits_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates and sends the habits report for the selected period."""
    period_text = update.message.text

    period_map = {
        "Today": "today",
        "This Week": "this_week",
        "Last Week": "last_week",
        "This Month": "this_month",
        "Last Month": "last_month",
        "Custom Range": "custom"
    }

    period = period_map.get(period_text)
    if not period:
        await update.message.reply_text("Invalid choice. Please select from the keyboard.", reply_markup=keyboards.report_period_keyboard())
        return CHOOSE_HABITS_PERIOD

    if period == "custom":
        await update.message.reply_text(
            "Custom date range is not available for habits analysis. Please select a standard period.",
            reply_markup=keyboards.report_period_keyboard())
        return CHOOSE_HABITS_PERIOD

    today = datetime.now(PHNOM_PENH_TZ).date()
    end_of_last_month = today.replace(day=1) - timedelta(days=1)
    start_of_last_month = end_of_last_month.replace(day=1)
    date_ranges = {
        "today": (today, today),
        "this_week": (today - timedelta(days=today.weekday()),
                      today - timedelta(days=today.weekday()) + timedelta(days=6)),
        "last_week": (today - timedelta(days=today.weekday() + 7), today - timedelta(days=today.weekday() + 1)),
        "this_month": (today.replace(day=1),
                       (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)),
        "last_month": (start_of_last_month, end_of_last_month)
    }

    date_pair = date_ranges.get(period)
    if date_pair:
        start_date, end_date = date_pair
        loading_msg = await update.message.reply_text("🧠 Analyzing your habits...", reply_markup=keyboards.main_menu_keyboard())
        habits_data = api_client.get_spending_habits(start_date, end_date)
        await loading_msg.delete()

        if habits_data:
            message = _format_habits_message(habits_data)
            await update.message.reply_text(text=message, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())
        else:
            await update.message.reply_text("Could not find enough data to analyze your habits for this period.",
                                            reply_markup=keyboards.main_menu_keyboard())
    else:
        await update.message.reply_text("Invalid period selected.", reply_markup=keyboards.main_menu_keyboard())

    return ConversationHandler.END