# --- Start of file: telegram_bot/handlers/utility.py ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import keyboards
import api_client
from decorators import restricted
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from .helpers import format_summary_message
import os

# Conversation states
(
    NEW_RATE,
    SETBALANCE_ACCOUNT, SETBALANCE_AMOUNT,
    REMINDER_PURPOSE, REMINDER_ASK_DATE, REMINDER_CUSTOM_DATE, REMINDER_ASK_TIME
) = range(7)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")

# --- Regex for buttons ---
SETBALANCE_ACC_REGEX = '^(💵 USD Account|៛ KHR Account)$'
REMINDER_DATE_REGEX = '^(Tomorrow|In 3 Days|In 1 Week|Custom Date)$'


# --- Rate Update Conversation ---
@restricted
async def update_rate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Please enter the new exchange rate for 1 USD to KHR (e.g., 4100).\n"
        "This will be used as a fallback if the live API fails.",
        reply_markup=keyboards.HIDE_KEYBOARD
    )
    return NEW_RATE


async def received_new_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_rate = float(update.message.text)
        if api_client.update_exchange_rate(new_rate):
            await update.message.reply_text(f"✅ Fallback exchange rate updated to {new_rate}",
                                            reply_markup=keyboards.main_menu_keyboard())
        else:
            await update.message.reply_text("❌ Failed to update the rate.", reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END
    except (ValueError, TypeError):
        await update.message.reply_text("Invalid number. Please enter a valid rate.")
        return NEW_RATE


@restricted
async def get_current_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays the current LIVE exchange rate."""
    loading_msg = await update.message.reply_text("Fetching live rate...")
    data = api_client.get_exchange_rate()

    if data and 'rate' in data:
        rate = data['rate']
        text = f"📈 The current **live** exchange rate is:\n<b>1 USD = {rate:,.0f} KHR</b>"
    else:
        text = "❌ Could not fetch the live exchange rate. Using fallback."

    await loading_msg.edit_text(
        text=text,
        parse_mode='HTML'
    )
    # Send main keyboard separately
    await update.message.reply_text("Rate check complete.", reply_markup=keyboards.main_menu_keyboard())


# --- Set Initial Balance Conversation ---
@restricted
async def set_balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Which account balance do you want to set?",
                                    reply_markup=keyboards.set_balance_account_keyboard())
    return SETBALANCE_ACCOUNT


async def received_balance_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    currency = "USD" if choice == "💵 USD Account" else "KHR"
    context.user_data['currency'] = currency
    await update.message.reply_text(f"Account: <b>{currency}</b>\n\nWhat is the total current balance?",
                                    parse_mode='HTML', reply_markup=keyboards.HIDE_KEYBOARD)
    return SETBALANCE_AMOUNT


async def received_balance_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        tx_data = {
            "type": "income", "amount": amount,
            "currency": context.user_data['currency'],
            "accountName": f"{context.user_data['currency']} Account",
            "categoryId": "Initial Balance",
            "description": "Starting balance set by user"
        }
        api_client.add_transaction(tx_data)
        summary_text = format_summary_message(api_client.get_detailed_summary())
        await update.message.reply_text(
            f"✅ Initial balance of {amount:,.2f} {context.user_data['currency']} set!{summary_text}", parse_mode='HTML',
            reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END
    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid number for the balance.")
        return SETBALANCE_AMOUNT


# --- Set Reminder Conversation ---
@restricted
async def set_reminder_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("What would you like to be reminded of?", reply_markup=keyboards.HIDE_KEYBOARD)
    return REMINDER_PURPOSE


async def received_reminder_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reminder_purpose'] = update.message.text
    await update.message.reply_text("When should I remind you?", reply_markup=keyboards.reminder_date_keyboard())
    return REMINDER_ASK_DATE


async def received_reminder_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text

    days_map = {
        "Tomorrow": 1,
        "In 3 Days": 3,
        "In 1 Week": 7
    }

    if choice == 'Custom Date':
        await update.message.reply_text("Please enter the date in YYYY-MM-DD format.", reply_markup=keyboards.HIDE_KEYBOARD)
        return REMINDER_CUSTOM_DATE

    days = days_map.get(choice)
    if not days:
        await update.message.reply_text("Invalid choice.", reply_markup=keyboards.reminder_date_keyboard())
        return REMINDER_ASK_DATE

    reminder_date = datetime.now(PHNOM_PENH_TZ).date() + timedelta(days=int(days))
    context.user_data['reminder_date_part'] = reminder_date
    await update.message.reply_text("Got it. And at what time? (e.g., 09:00, 17:30)", reply_markup=keyboards.HIDE_KEYBOARD)
    return REMINDER_ASK_TIME


async def received_reminder_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        custom_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['reminder_date_part'] = custom_date
        await update.message.reply_text("Got it. And at what time? (e.g., 09:00, 17:30)", reply_markup=keyboards.HIDE_KEYBOARD)
        return REMINDER_ASK_TIME
    except ValueError:
        await update.message.reply_text("Invalid format. Please use YYYY-MM-DD.")
        return REMINDER_CUSTOM_DATE


async def received_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        reminder_time = datetime.strptime(update.message.text, "%H:%M").time()
        reminder_date = context.user_data['reminder_date_part']
        aware_dt = datetime.combine(reminder_date, reminder_time, tzinfo=PHNOM_PENH_TZ)
        context.user_data['reminder_datetime'] = aware_dt.isoformat()

        target_chat_id = os.getenv("REMINDER_TARGET_CHAT_ID") or update.effective_chat.id

        reminder_data = {
            "purpose": context.user_data['reminder_purpose'],
            "reminder_datetime": context.user_data['reminder_datetime'],
            "chat_id": target_chat_id
        }

        api_client.add_reminder(reminder_data)
        await update.message.reply_text(f"✅ Got it! I will remind you on {aware_dt.strftime('%d %b %Y at %H:%M')}.",
                                        reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Invalid time format. Please use HH:MM (24-hour).")
        return REMINDER_ASK_TIME