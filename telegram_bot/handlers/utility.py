# --- Start of file: telegram_bot/handlers/utility.py ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import keyboards
import api_client
from decorators import authenticate_user # <-- MODIFICATION: Fix import
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from .helpers import format_summary_message
import os
from utils.i18n import t

# Conversation states
(
    NEW_RATE,
    SETBALANCE_ACCOUNT, SETBALANCE_AMOUNT,
    REMINDER_PURPOSE, REMINDER_ASK_DATE, REMINDER_CUSTOM_DATE, REMINDER_ASK_TIME
) = range(7)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")


@authenticate_user # <-- MODIFICATION
async def get_current_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays the current LIVE exchange rate."""
    query = update.callback_query
    await query.answer("Fetching rate...")

    # --- REFACTOR: Get JWT ---
    jwt = context.user_data['jwt']
    data = api_client.get_exchange_rate(jwt) # <-- MODIFICATION
    # ---

    if data and 'rate' in data:
        rate = data['rate']
        source = data.get('source', 'live')
        text = t("utility.rate_header", context, source=source, rate=rate)
    else:
        text = t("utility.rate_fail", context)

    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard(context)
    )


# --- Set Reminder Conversation ---
@authenticate_user # <-- MODIFICATION
async def set_reminder_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # --- THIS IS THE FIX ---
    # We no longer need to clear the context.
    # --- END FIX ---

    await query.message.reply_text(t("utility.remind_what", context))
    return REMINDER_PURPOSE


@authenticate_user # <-- MODIFICATION
async def received_reminder_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reminder_purpose'] = update.message.text
    await update.message.reply_text(
        t("utility.remind_when", context),
        reply_markup=keyboards.reminder_date_keyboard(context)
    )
    return REMINDER_ASK_DATE


@authenticate_user # <-- MODIFICATION
async def received_reminder_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split('_')[-1]
    if choice == 'custom':
        await query.message.reply_text(t("utility.remind_ask_date", context))
        return REMINDER_CUSTOM_DATE

    reminder_date = datetime.now(PHNOM_PENH_TZ).date() + timedelta(days=int(choice))
    context.user_data['reminder_date_part'] = reminder_date
    await query.message.reply_text(t("utility.remind_ask_time", context))
    return REMINDER_ASK_TIME


@authenticate_user # <-- MODIFICATION
async def received_reminder_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        custom_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['reminder_date_part'] = custom_date
        await update.message.reply_text(t("utility.remind_ask_time", context))
        return REMINDER_ASK_TIME
    except ValueError:
        await update.message.reply_text(t("utility.remind_invalid_date", context))
        return REMINDER_CUSTOM_DATE


@authenticate_user # <-- MODIFICATION
async def received_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # --- REFACTOR: Get JWT and profile ---
        jwt = context.user_data['jwt']
        profile = context.user_data['profile']
        # ---

        # Use the user's specific reminder chat ID, or fall back to the current chat
        target_chat_id = profile.get('settings', {}).get('notification_chat_ids', {}).get('reminder') or update.effective_chat.id
        # ---

        reminder_time = datetime.strptime(update.message.text, "%H:%M").time()
        reminder_date = context.user_data['reminder_date_part']
        aware_dt = datetime.combine(reminder_date, reminder_time, tzinfo=PHNOM_PENH_TZ)
        context.user_data['reminder_datetime'] = aware_dt.isoformat()

        reminder_data = {
            "purpose": context.user_data['reminder_purpose'],
            "reminder_datetime": context.user_data['reminder_datetime'],
            "chat_id": target_chat_id
        }

        # --- REFACTOR: Pass JWT ---
        api_client.add_reminder(reminder_data, jwt)
        # ---

        await update.message.reply_text(
            t("utility.remind_success", context, date_time=aware_dt.strftime('%d %b %Y at %H:%M')),
            reply_markup=keyboards.main_menu_keyboard(context)
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(t("utility.remind_invalid_time", context))
        return REMINDER_ASK_TIME
# --- End of file ---