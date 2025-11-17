from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import keyboards
import api_client
from decorators import authenticate_user
from .helpers import (
    _format_report_summary_message,
    _create_income_expense_chart,
    _create_expense_pie_chart,
    _format_habits_message,
    _create_spending_line_chart,
    _create_csv_from_transactions
)
from utils.i18n import t
from api_client import PremiumFeatureException

(
    CHOOSE_REPORT_PERIOD, REPORT_ASK_START_DATE, REPORT_ASK_END_DATE,
    CHOOSE_HABITS_PERIOD
) = range(4)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")


@authenticate_user
async def report_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        t("analytics.report_ask_period", context),
        reply_markup=keyboards.report_period_keyboard(context)
    )
    return CHOOSE_REPORT_PERIOD


@authenticate_user
async def process_report_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    period = query.data.replace('report_period_', '')

    if period == "custom":
        await query.edit_message_text(t("analytics.report_ask_start", context))
        return REPORT_ASK_START_DATE

    # Calculate dates
    today = datetime.now(PHNOM_PENH_TZ).date()
    start, end = today, today

    if period == 'this_week':
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif period == 'last_week':
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
    elif period == 'this_month':
        start = today.replace(day=1)
        next_m = start.replace(day=28) + timedelta(days=4)
        end = next_m - timedelta(days=next_m.day)
    elif period == 'last_month':
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)

    await _generate_report(update, context, start, end)
    return ConversationHandler.END


@authenticate_user
async def received_report_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dt = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['report_start'] = dt
        await update.message.reply_text(t("analytics.report_ask_end", context, date=dt))
        return REPORT_ASK_END_DATE
    except ValueError:
        await update.message.reply_text(t("analytics.report_invalid_date", context))
        return REPORT_ASK_START_DATE


@authenticate_user
async def received_report_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        end = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        start = context.user_data.pop('report_start', None)

        if not start or end < start:
            await update.message.reply_text(t("analytics.report_invalid_range", context))
            return REPORT_ASK_END_DATE

        await _generate_report(update, context, start, end)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(t("analytics.report_invalid_date", context))
        return REPORT_ASK_END_DATE


async def _generate_report(update, context, start, end):
    msg = update.callback_query.message if update.callback_query else update.message
    loading = await msg.reply_text(t("analytics.report_generating", context, start_date=start, end_date=end))

    try:
        data = api_client.get_detailed_report(context.user_data['jwt'], start, end)
        await loading.delete()

        if not data or "error" in data:
            await context.bot.send_message(msg.chat.id, t("analytics.report_fail", context),
                                           reply_markup=keyboards.main_menu_keyboard(context))
            return

        summary = _format_report_summary_message(data, context)
        await context.bot.send_message(msg.chat.id, summary, parse_mode='HTML')

        # Charts
        if bar := _create_income_expense_chart(data, start, end):
            await context.bot.send_photo(msg.chat.id, bar)
        if line := _create_spending_line_chart(data, start, end):
            await context.bot.send_photo(msg.chat.id, line)
        if pie := _create_expense_pie_chart(data, start, end):
            await context.bot.send_photo(msg.chat.id, pie)

        await context.bot.send_message(msg.chat.id, t("analytics.report_success", context),
                                       reply_markup=keyboards.report_actions_keyboard(start, end, context))

    except PremiumFeatureException:
        await loading.delete()
        await context.bot.send_message(msg.chat.id, t("common.premium_required", context),
                                       reply_markup=keyboards.main_menu_keyboard(context))
    except Exception as e:
        await loading.delete()
        await context.bot.send_message(msg.chat.id, f"Error: {e}", reply_markup=keyboards.main_menu_keyboard(context))


# --- Habits ---

@authenticate_user
async def habits_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        t("analytics.habits_ask_period", context),
        reply_markup=keyboards.report_period_keyboard(context)
    )
    return CHOOSE_HABITS_PERIOD


@authenticate_user
async def process_habits_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    period = query.data.replace('report_period_', '')

    if period == 'custom':
        await query.edit_message_text(t("analytics.habits_no_custom", context),
                                      reply_markup=keyboards.report_period_keyboard(context))
        return CHOOSE_HABITS_PERIOD

    # Reuse date logic (simplified duplication here for isolation)
    today = datetime.now(PHNOM_PENH_TZ).date()
    start, end = today, today

    if period == 'this_week':
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif period == 'last_week':
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
    elif period == 'this_month':
        start = today.replace(day=1)
        next_m = start.replace(day=28) + timedelta(days=4)
        end = next_m - timedelta(days=next_m.day)
    elif period == 'last_month':
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)

    await query.edit_message_text(t("analytics.habits_generating", context))

    try:
        data = api_client.get_spending_habits(context.user_data['jwt'], start, end)
        if not data or "error" in data:
            await query.edit_message_text(t("analytics.habits_fail", context),
                                          reply_markup=keyboards.main_menu_keyboard(context))
            return

        await query.edit_message_text(_format_habits_message(data), parse_mode='HTML',
                                      reply_markup=keyboards.main_menu_keyboard(context))

    except PremiumFeatureException:
        await query.edit_message_text(t("common.premium_required", context),
                                      reply_markup=keyboards.main_menu_keyboard(context))
    except Exception as e:
        await query.edit_message_text(f"Error: {e}", reply_markup=keyboards.main_menu_keyboard(context))

    return ConversationHandler.END


@authenticate_user
async def download_report_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(t("search.searching", context))

    try:
        _, s_str, e_str = query.data.split(':')

        # Use search API to get raw data
        txs = api_client.search_transactions_for_management(
            {'start_date': s_str, 'end_date': e_str},
            context.user_data['jwt']
        )

        if not txs:
            await query.message.reply_text(t("search.no_results", context))
            return

        csv_file = _create_csv_from_transactions(txs)
        fname = f"report_{s_str}_to_{e_str}.csv"

        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=csv_file,
            filename=fname,
            caption=f"Transaction Export: {s_str} to {e_str}"
        )
    except Exception as e:
        await query.message.reply_text(t("common.error_generic", context, error=str(e)))