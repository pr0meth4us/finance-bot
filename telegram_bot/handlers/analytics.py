# --- Start of modified file: telegram_bot/handlers/analytics.py ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import keyboards
import api_client
from decorators import authenticate_user
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from .helpers import (
    _format_report_summary_message,
    _create_income_expense_chart,
    _create_expense_pie_chart,
    _format_habits_message,
    _create_spending_line_chart,
    _create_csv_from_transactions  # <-- NEW IMPORT
)
from utils.i18n import t

(
    CHOOSE_REPORT_PERIOD, REPORT_ASK_START_DATE, REPORT_ASK_END_DATE,
    CHOOSE_HABITS_PERIOD
) = range(4)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
REPORT_PERIOD_REGEX = '^(Today|This Week|Last Week|This Month|Last Month|Custom Range)$'


@authenticate_user
async def report_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the menu for selecting a report period."""
    query = update.callback_query
    await query.answer()

    # --- THIS IS THE FIX ---
    # Preserve the user_profile, clear everything else, then restore it.
    user_profile = context.user_data.get('user_profile')
    context.user_data.clear()
    context.user_data['user_profile'] = user_profile
    # --- END FIX ---

    await query.edit_message_text(
        t("analytics.report_ask_period", context),
        reply_markup=keyboards.report_period_keyboard(context)
    )
    return CHOOSE_REPORT_PERIOD


@authenticate_user
async def process_report_choice(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    """Handles standard period selection or transitions to custom date entry."""
    query = update.callback_query
    await query.answer()
    period = query.data.replace('report_period_', '')

    if period == "custom":
        await query.edit_message_text(t("analytics.report_ask_start", context))
        return REPORT_ASK_START_DATE

    today = datetime.now(PHNOM_PENH_TZ).date()
    end_of_last_month = today.replace(day=1) - timedelta(days=1)
    start_of_last_month = end_of_last_month.replace(day=1)
    date_ranges = {
        "today": (today, today),
        "this_week": (today - timedelta(days=today.weekday()),
                      today - timedelta(days=today.weekday()) +
                      timedelta(days=6)),
        "last_week": (today - timedelta(days=today.weekday() + 7),
                      today - timedelta(days=today.weekday() + 1)),
        "this_month": (today.replace(day=1),
                       (today.replace(day=28) +
                        timedelta(days=4)).replace(day=1) -
                       timedelta(days=1)),
        "last_month": (start_of_last_month, end_of_last_month)
    }

    date_pair = date_ranges.get(period)
    if date_pair:
        start_date, end_date = date_pair
        await _generate_report(update, context, start_date, end_date)
    else:
        await query.edit_message_text(
            t("analytics.habits_invalid_period", context),
            reply_markup=keyboards.main_menu_keyboard(context)
        )

    return ConversationHandler.END


@authenticate_user
async def received_report_start_date(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
    """Receives and validates the custom start date."""
    try:
        start_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['report_start_date'] = start_date
        await update.message.reply_text(
            t("analytics.report_ask_end", context, date=start_date)
        )
        return REPORT_ASK_END_DATE
    except ValueError:
        await update.message.reply_text(
            t("analytics.report_invalid_date", context)
        )
        return REPORT_ASK_START_DATE


@authenticate_user
async def received_report_end_date(update: Update,
                                   context: ContextTypes.DEFAULT_TYPE):
    """Receives, validates end date, and generates the report."""
    try:
        end_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        start_date = context.user_data.get('report_start_date')
        if not start_date or end_date < start_date:
            await update.message.reply_text(
                t("analytics.report_invalid_range", context)
            )
            return REPORT_ASK_END_DATE
        await _generate_report(update, context, start_date, end_date)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            t("analytics.report_invalid_date", context)
        )
        return REPORT_ASK_END_DATE
    finally:
        context.user_data.pop('report_start_date', None)


async def _generate_report(update: Update,
                           context: ContextTypes.DEFAULT_TYPE,
                           start_date, end_date):
    """Shared logic to generate and send report summary and charts."""
    chat_id = update.effective_chat.id
    user_id = context.user_data['user_profile']['_id']

    loading_text = t("analytics.report_generating", context,
                     start_date=start_date, end_date=end_date)

    loading_message = await context.bot.send_message(
        chat_id=chat_id, text=loading_text
    )
    if update.callback_query:
        await update.callback_query.message.delete()

    report_data = api_client.get_detailed_report(user_id, start_date, end_date)
    await loading_message.delete()

    if report_data:
        summary_message = _format_report_summary_message(report_data)
        await context.bot.send_message(
            chat_id=chat_id, text=summary_message, parse_mode='HTML'
        )

        if bar_chart := _create_income_expense_chart(
                report_data, start_date, end_date):
            await context.bot.send_photo(chat_id=chat_id, photo=bar_chart)
        if line_chart := _create_spending_line_chart(
                report_data, start_date, end_date):
            await context.bot.send_photo(chat_id=chat_id, photo=line_chart)
        if pie_chart := _create_expense_pie_chart(
                report_data, start_date, end_date):
            await context.bot.send_photo(chat_id=chat_id, photo=pie_chart)

        await context.bot.send_message(
            chat_id=chat_id,
            text=t("analytics.report_success", context),
            # --- MODIFICATION: Use new keyboard ---
            reply_markup=keyboards.report_actions_keyboard(
                start_date, end_date, context
            )
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=t("analytics.report_fail", context),
            reply_markup=keyboards.main_menu_keyboard(context)
        )


@authenticate_user
async def habits_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays menu to choose a period for habits analysis."""
    query = update.callback_query
    await query.answer()

    # --- THIS IS THE FIX ---
    # Preserve the user_profile, clear everything else, then restore it.
    user_profile = context.user_data.get('user_profile')
    context.user_data.clear()
    context.user_data['user_profile'] = user_profile
    # --- END FIX ---

    await query.edit_message_text(
        t("analytics.habits_ask_period", context),
        reply_markup=keyboards.report_period_keyboard(context)
    )
    return CHOOSE_HABITS_PERIOD


@authenticate_user
async def process_habits_choice(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    """Generates and sends the habits report for the selected period."""
    query = update.callback_query
    await query.answer()
    period = query.data.replace('report_period_', '')

    if period == "custom":
        await query.edit_message_text(
            t("analytics.habits_no_custom", context),
            reply_markup=keyboards.report_period_keyboard(context)
        )
        return CHOOSE_HABITS_PERIOD

    today = datetime.now(PHNOM_PENH_TZ).date()
    end_of_last_month = today.replace(day=1) - timedelta(days=1)
    start_of_last_month = end_of_last_month.replace(day=1)
    date_ranges = {
        "today": (today, today),
        "this_week": (today - timedelta(days=today.weekday()),
                      today - timedelta(days=today.weekday()) +
                      timedelta(days=6)),
        "last_week": (today - timedelta(days=today.weekday() + 7),
                      today - timedelta(days=today.weekday() + 1)),
        "this_month": (today.replace(day=1),
                       (today.replace(day=28) +
                        timedelta(days=4)).replace(day=1) -
                       timedelta(days=1)),
        "last_month": (start_of_last_month, end_of_last_month)
    }

    date_pair = date_ranges.get(period)
    if date_pair:
        start_date, end_date = date_pair
        await query.edit_message_text(
            t("analytics.habits_generating", context)
        )

        user_id = context.user_data['user_profile']['_id']
        habits_data = api_client.get_spending_habits(
            user_id, start_date, end_date
        )

        if habits_data:
            message = _format_habits_message(habits_data)
            await query.edit_message_text(
                text=message,
                parse_mode='HTML',
                reply_markup=keyboards.main_menu_keyboard(context)
            )
        else:
            await query.edit_message_text(
                t("analytics.habits_fail", context),
                reply_markup=keyboards.main_menu_keyboard(context)
            )
    else:
        await query.edit_message_text(
            t("analytics.habits_invalid_period", context),
            reply_markup=keyboards.main_menu_keyboard(context)
        )

    return ConversationHandler.END


# --- NEW HANDLER FOR CSV EXPORT ---
@authenticate_user
async def download_report_csv(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    """Handles the 'Download Report CSV' button press."""
    query = update.callback_query
    await query.answer(t("search.searching", context))

    try:
        user_id = context.user_data['user_profile']['_id']
        _, start_date_str, end_date_str = query.data.split(':')
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()

        search_params = {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }

        # Use the existing search API to get all raw transactions
        transactions = api_client.search_transactions_for_management(
            search_params, user_id
        )

        if not transactions:
            await query.message.reply_text(t("search.no_results", context))
            return

        # Generate CSV
        csv_buffer = _create_csv_from_transactions(transactions)
        file_name = f"report_{start_date.isoformat()}_to_{end_date.isoformat()}.csv"

        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=csv_buffer,
            filename=file_name,
            caption=f"Here is your transaction export for {start_date} to {end_date}."
        )

    except Exception as e:
        print(f"Error generating report CSV: {e}")
        await query.message.reply_text(t("common.error_generic", context, error=str(e)))

# --- End of modified file ---