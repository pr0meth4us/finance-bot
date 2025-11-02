# --- Start of corrected file: telegram_bot/handlers/command_handler.py ---

from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters, CommandHandler
)
import api_client
import keyboards
from decorators import restricted
from .helpers import format_summary_message
from .common import cancel, start
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import shlex
import re

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
SELECT_CATEGORY, GET_CUSTOM_CATEGORY = range(2)

COMMAND_MAP = {
    'coffee': {'categoryId': 'Drink', 'description': 'Coffee', 'type': 'expense'},
    'lunch': {'categoryId': 'Food', 'description': 'Lunch', 'type': 'expense'},
    'dinner': {'categoryId': 'Food', 'description': 'Dinner', 'type': 'expense'},
    'gas': {'categoryId': 'Transport', 'description': 'Gas', 'type': 'expense'},
    'parking': {'categoryId': 'Transport', 'description': 'Parking', 'type': 'expense'},
    'taxi': {'categoryId': 'Transport', 'description': 'Taxi/Tuktuk', 'type': 'expense'},
    'movie': {'categoryId': 'Entertainment', 'description': 'Movie', 'type': 'expense'},
    'groceries': {'categoryId': 'Shopping', 'description': 'Groceries', 'type': 'expense'},
    'shopping': {'categoryId': 'Shopping', 'description': 'Shopping', 'type': 'expense'},
    'bills': {'categoryId': 'Bills', 'description': 'Bills', 'type': 'expense'},
    'pizza': {'categoryId': 'Food', 'description': 'Pizza', 'type': 'expense'},
    'others': {'categoryId': 'For Others', 'description': 'For Others', 'type': 'expense'},
    'alcohol': {'categoryId': 'Alcohol', 'description': 'Alcohol', 'type': 'expense'},
    'salary': {'categoryId': 'Salary', 'description': 'Salary', 'type': 'income'},
    'bonus': {'categoryId': 'Bonus', 'description': 'Bonus', 'type': 'income'},
    'commission': {'categoryId': 'Commission', 'description': 'Commission', 'type': 'income'},
    'allowance': {'categoryId': 'Allowance', 'description': 'Allowance', 'type': 'income'},
    'gift': {'categoryId': 'Gift', 'description': 'Gift', 'type': 'income'},
}

def parse_date_from_list(args_list):
    """Tries to find and remove a MM-DD date from the end of the list."""
    if not args_list: return None, args_list
    try:
        date_str = args_list[-1]
        datetime.strptime(date_str, '%m-%d') # Just to check format
        today = datetime.now(PHNOM_PENH_TZ)
        parsed_date = datetime.strptime(f"{today.year}-{date_str}", '%Y-%m-%d')
        tx_datetime = today.replace(month=parsed_date.month, day=parsed_date.day, hour=12, minute=0, second=0, microsecond=0)
        return tx_datetime.isoformat(), args_list[:-1] # Return date and remaining args
    except (ValueError, TypeError):
        return None, args_list

def find_and_parse_amount_from_list(args_list):
    """Finds the first parsable amount in a list, removes it, and returns it."""
    for i, arg in enumerate(args_list):
        try:
            # This regex checks for a number, optional decimal, and optional 'khr'
            if re.fullmatch(r'^\.?\d+(\.\d+)?(khr)?$', arg.lower()):
                amount_str = args_list.pop(i)
                amount, currency = parse_amount_and_currency(amount_str)
                return amount, currency, args_list
        except ValueError:
            continue
    return None, None, args_list # No amount found

def parse_amount_and_currency(amount_str):
    amount_str = amount_str.lower()
    if 'khr' in amount_str:
        return float(amount_str.replace('khr', '').strip()), 'KHR'
    else:
        return float(amount_str), 'USD'

# --- MAIN MESSAGE ROUTER ---
@restricted
async def unified_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_text = update.message.text
    logger.info(f"--- Message router received text: '{full_text}' ---")

    try:
        args_str_fixed = full_text.replace('“', '"').replace('”', '"')
        parts = shlex.split(args_str_fixed)

        if not parts:
            return ConversationHandler.END # Ignore empty messages

        trigger_word = parts[0].lower()
        args = parts[1:]

        # --- Route to specific handlers based on trigger word ---

        # 1. Repayment
        if trigger_word in ["paid", "repaid"] or full_text.lower().startswith("repaid by"):
            if full_text.lower().startswith("repaid by"):
                args = parts[2:] # Remove "repaid by"
            await handle_repayment(update, args)

        # 2. Generic Expense/Income
        elif trigger_word in ["expense", "income"]:
            tx_data, base_text = await handle_generic_transaction(update, trigger_word, args)
            if tx_data: api_client.add_transaction(tx_data)

        # 3. Generic Debt/Loan
        elif trigger_word in ["lent", "borrowed"]:
            debt_data, base_text = await handle_generic_debt(update, trigger_word, args)
            if debt_data: api_client.add_debt(debt_data)

        # 4. Quick Command
        elif trigger_word in COMMAND_MAP:
            tx_data, base_text = await handle_quick_command(update, trigger_word, args)
            if tx_data: api_client.add_transaction(tx_data)

        # 5. Unknown Command (Start conversation)
        else:
            context.user_data['unknown_command_data'] = {'command': trigger_word, 'args': args}
            return await unknown_command_entry_point(update, context)

        # If a one-liner was processed, send summary and end
        summary_text = format_summary_message(api_client.get_detailed_summary())
        await update.message.reply_text(summary_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in unified_message_router: {e}", exc_info=True)
        await update.message.reply_text("An error occurred. Please check the format.")
        return ConversationHandler.END

# --- INDIVIDUAL COMMAND LOGIC FUNCTIONS ---

async def handle_generic_transaction(update: Update, command, args):
    tx_date, remaining_args = parse_date_from_args(args)
    amount, currency, remaining_args = find_and_parse_amount_from_list(remaining_args)

    if amount is None or not remaining_args:
        await update.message.reply_text(f"⚠️ Format: `{command} <Category> [Description] <Amount> [MM-DD]`", parse_mode='Markdown')
        return None, None

    category = remaining_args[0]
    description = " ".join(remaining_args[1:])
    tx_data = { "type": command, "amount": amount, "currency": currency, "accountName": f"{currency} Account", "categoryId": category, "description": description, "timestamp": tx_date }
    return tx_data, f"✅ Generic {command} recorded!"

async def handle_generic_debt(update: Update, command, args):
    tx_date, remaining_args = parse_date_from_args(args)
    amount, currency, remaining_args = find_and_parse_amount_from_list(remaining_args)

    if amount is None or not remaining_args:
        await update.message.reply_text(f"⚠️ Format: `{command} <Person> <Amount> [Purpose] [MM-DD]`", parse_mode='Markdown')
        return None, None

    person = remaining_args[0]
    purpose = " ".join(remaining_args[1:])
    debt_data = { "type": command, "person": person, "amount": amount, "currency": currency, "purpose": purpose, "timestamp": tx_date }
    return debt_data, f"✅ {command.title()} record saved!"

async def handle_quick_command(update: Update, command, args):
    tx_date, remaining_args = parse_date_from_args(args)
    amount, currency, description_parts = find_and_parse_amount_from_list(remaining_args)

    if amount is None:
        await update.message.reply_text(f"⚠️ Invalid format. Amount is missing for `/{command}`.", parse_mode='Markdown')
        return None, None

    details = COMMAND_MAP[command]
    description = " ".join(description_parts) if description_parts else details['description']

    tx_data = { "type": details['type'], "amount": amount, "currency": currency, "accountName": f"{currency} Account", "categoryId": details['categoryId'], "description": description, "timestamp": tx_date }
    return tx_data, "✅ Quick transaction recorded!"

async def handle_repayment(update: Update, args):
    try:
        tx_date, remaining_args = parse_date_from_args(args) # Date is not used by API but good to parse
        amount, currency, remaining_args = find_and_parse_amount_from_list(remaining_args)

        if amount is None or not remaining_args:
            await update.message.reply_text(f"⚠️ Format: `paid <Person> <Amount> [MM-DD]`", parse_mode='Markdown')
            return

        person = " ".join(remaining_args) # The rest of the args are the person's name

        response = api_client.record_lump_sum_repayment(person, currency, amount)
        base_text = response.get('message')
        if not base_text:
            base_text = f"❌ Error: {response.get('error', 'Could not process repayment.')}"

    except Exception as e:
        logger.error(f"Error in handle_repayment: {e}", exc_info=True)
        base_text = "⚠️ Invalid format for repayment command."

    summary_text = format_summary_message(api_client.get_detailed_summary())
    await update.message.reply_text(base_text + summary_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())

# --- UNKNOWN ITEM CONVERSATION ---
async def unknown_command_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = context.user_data['unknown_command_data']
        command, args = data['command'], data['args']

        tx_date, args_without_date = parse_date_from_args(args)
        amount, currency, description_parts = find_and_parse_amount_from_list(args_without_date)

        if amount is None:
            await update.message.reply_text(f"I see '{command}' but no amount. To log an expense, please provide an amount.", parse_mode='Markdown')
            return ConversationHandler.END

        # Use the command and any other words as the description
        description = f"{command} {' '.join(description_parts)}".strip().title()

        context.user_data['new_tx'] = {"type": "expense", "amount": amount, "currency": currency, "accountName": f"{currency} Account", "description": description, "timestamp": tx_date}
        amount_display = f"{amount:,.0f} {currency}" if currency == 'KHR' else f"${amount:,.2f}"

        await update.message.reply_text(f"New expense '{description}' for {amount_display}. Which category?", reply_markup=keyboards.expense_categories_keyboard())
        return SELECT_CATEGORY
    except Exception as e:
        logger.error(f"Error starting unknown command flow: {e}", exc_info=True)
        return ConversationHandler.END

async def received_category_for_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split('_')[1]

    if category == 'other':
        await query.edit_message_text("Please type your new custom category name:")
        return GET_CUSTOM_CATEGORY

    tx_data = context.user_data.get('new_tx')
    if not tx_data: return ConversationHandler.END

    tx_data['categoryId'] = category
    return await save_and_end_unknown(query.message, tx_data)

async def received_text_for_custom_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tx_data = context.user_data.get('new_tx')
    if not tx_data: return ConversationHandler.END

    tx_data['categoryId'] = update.message.text.strip().title()
    return await save_and_end_unknown(update.message, tx_data)

async def save_and_end_unknown(message, tx_data):
    response = api_client.add_transaction(tx_data)
    base_text = "✅ New transaction recorded!" if response else "❌ Failed to record."
    summary_text = format_summary_message(api_client.get_detailed_summary())
    await message.reply_text(base_text + summary_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

# This is the main handler for all non-command text
unified_message_conversation_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, unified_message_router)],
    states={
        SELECT_CATEGORY: [CallbackQueryHandler(received_category_for_unknown, pattern='^cat_')],
        GET_CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_text_for_custom_category)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_message=False,
    conversation_timeout=60
)