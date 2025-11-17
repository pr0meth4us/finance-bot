from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import keyboards
import api_client
from decorators import authenticate_user
from utils.i18n import t

(
    NEW_RATE, SETBALANCE_ACCOUNT, SETBALANCE_AMOUNT,
    REMINDER_PURPOSE, REMINDER_ASK_DATE, REMINDER_CUSTOM_DATE, REMINDER_ASK_TIME
) = range(7)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")


@authenticate_user
async def get_current_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Fetching rate...")

    data = api_client.get_exchange_rate(context.user_data['jwt'])

    if data and 'rate' in data:
        text = t("utility.rate_header", context, source=data.get('source', 'live'), rate=data['rate'])
    else:
        text = t("utility.rate_fail", context)

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard(context))


# --- Reminders ---

@authenticate_user
async def set_reminder_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(t("utility.remind_what", context))
    return REMINDER_PURPOSE


@authenticate_user
async def received_reminder_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reminder_purpose'] = update.message.text
    await update.message.reply_text(t("utility.remind_when", context),
                                    reply_markup=keyboards.reminder_date_keyboard(context))
    return REMINDER_ASK_DATE


@authenticate_user
async def received_reminder_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split('_')[-1]

    if choice == 'custom':
        await query.message.reply_text(t("utility.remind_ask_date", context))
        return REMINDER_CUSTOM_DATE

    dt = datetime.now(PHNOM_PENH_TZ).date() + timedelta(days=int(choice))
    context.user_data['reminder_date'] = dt
    await query.message.reply_text(t("utility.remind_ask_time", context))
    return REMINDER_ASK_TIME


@authenticate_user
async def received_reminder_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dt = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['reminder_date'] = dt
        await update.message.reply_text(t("utility.remind_ask_time", context))
        return REMINDER_ASK_TIME
    except ValueError:
        await update.message.reply_text(t("utility.remind_invalid_date", context))
        return REMINDER_CUSTOM_DATE


@authenticate_user
async def received_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tm = datetime.strptime(update.message.text, "%H:%M").time()
        dt = datetime.combine(context.user_data['reminder_date'], tm, tzinfo=PHNOM_PENH_TZ)

        # Check if user has specific reminder chat configured
        chats = context.user_data['profile'].get('settings', {}).get('notification_chat_ids', {})
        target_id = chats.get('reminder') or update.effective_chat.id

        payload = {
            "purpose": context.user_data['reminder_purpose'],
            "reminder_datetime": dt.isoformat(),
            "chat_id": target_id
        }

        api_client.add_reminder(payload, context.user_data['jwt'])

        await update.message.reply_text(
            t("utility.remind_success", context, date_time=dt.strftime('%d %b %Y at %H:%M')),
            reply_markup=keyboards.main_menu_keyboard(context)
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(t("utility.remind_invalid_time", context))
        return REMINDER_ASK_TIME