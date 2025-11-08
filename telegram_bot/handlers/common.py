# --- Start of modified file: telegram_bot/handlers/utility.py ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import keyboards
import api_client
from decorators import authenticate_user
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import os

# Conversation states
(
    REMINDER_PURPOSE,
    REMINDER_ASK_DATE,
    REMINDER_CUSTOM_DATE,
    REMINDER_ASK_TIME
) = range(4)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")


@authenticate_user
async def get_current_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays the current LIVE exchange rate."""
    query = update.callback_query
    await query.answer("Fetching rate...")

    user_id = context.user_data['user_profile']['_id']
    data = api_client.get_exchange_rate(user_id)

    if data and 'rate' in data:
        rate = data['rate']
        source = data.get('source', 'live')
        text = f"📈 Using **{source}** rate:\n<b>1 USD = {rate:,.0f} KHR</b>"
    else:
        text = "❌ Could not fetch the exchange rate."

    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard()
    )


# --- Set Reminder Conversation ---
@authenticate_user
async def set_reminder_start(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()
    context.user_data['user_profile'] = (
        context.application.user_data[update.effective_user.id]['user_profile']
    )

    await query.message.reply_text("What would you like to be reminded of?")
    return REMINDER_PURPOSE


@authenticate_user
async def received_reminder_purpose(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reminder_purpose'] = update.message.text
    await update.message.reply_text(
        "When should I remind you?",
        reply_markup=keyboards.reminder_date_keyboard()
    )
    return REMINDER_ASK_DATE


@authenticate_user
async def received_reminder_date_choice(update: Update,
                                        context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split('_')[-1]
    if choice == 'custom':
        await query.message.reply_text(
            "Please enter the date in YYYY-MM-DD format."
        )
        return REMINDER_CUSTOM_DATE

    reminder_date = datetime.now(PHNOM_PENH_TZ).date() + \
                    timedelta(days=int(choice))
    context.user_data['reminder_date_part'] = reminder_date
    await query.message.reply_text(
        "Got it. And at what time? (e.g., 09:00, 17:30)"
    )
    return REMINDER_ASK_TIME


@authenticate_user
async def received_reminder_custom_date(update: Update,
                                        context: ContextTypes.DEFAULT_TYPE):
    try:
        custom_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['reminder_date_part'] = custom_date
        await update.message.reply_text(
            "Got it. And at what time? (e.g., 09:00, 17:30)"
        )
        return REMINDER_ASK_TIME
    except ValueError:
        await update.message.reply_text("Invalid format. Please use YYYY-MM-DD.")
        return REMINDER_CUSTOM_DATE


@authenticate_user
async def received_reminder_time(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    try:
        user_profile = context.user_data['user_profile']
        user_id = user_profile['_id']

        target_chat_id = (
                user_profile.get('settings', {})
                .get('notification_chat_ids', {})
                .get('reminder') or update.effective_chat.id
        )

        reminder_time = datetime.strptime(update.message.text, "%H:%M").time()
        reminder_date = context.user_data['reminder_date_part']
        aware_dt = datetime.combine(
            reminder_date, reminder_time, tzinfo=PHNOM_PENH_TZ
        )
        context.user_data['reminder_datetime'] = aware_dt.isoformat()

        reminder_data = {
            "purpose": context.user_data['reminder_purpose'],
            "reminder_datetime": context.user_data['reminder_datetime'],
            "chat_id": target_chat_id
        }

        api_client.add_reminder(reminder_data, user_id)

        await update.message.reply_text(
            f"✅ Got it! I will remind you on "
            f"{aware_dt.strftime('%d %b %Y at %H:%M')}.",
            reply_markup=keyboards.main_menu_keyboard()
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "Invalid time format. Please use HH:MM (24-hour)."
        )
        return REMINDER_ASK_TIME
# --- End of modified file ---