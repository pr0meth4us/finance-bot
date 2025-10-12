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
# --- MODIFICATION START: Add safe evaluator for calculator ---
# NOTE: You must add 'asteval' to your requirements.txt
from asteval import Interpreter
# --- MODIFICATION END ---

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
SELECT_CATEGORY, GET_CUSTOM_CATEGORY = range(2)
# --- MODIFICATION START: Initialize the safe calculator ---
aeval = Interpreter()
# --- MODIFICATION END ---

COMMAND_MAP = {
    'coffee': {'categoryId': 'Drink', 'description': 'Coffee', 'type': 'expense'}, 'lunch': {'categoryId': 'Food', 'description': 'Lunch', 'type': 'expense'}, 'dinner': {'categoryId': 'Food', 'description': 'Dinner', 'type': 'expense'}, 'gas': {'categoryId': 'Transport', 'description': 'Gas', 'type': 'expense'}, 'parking': {'categoryId': 'Transport', 'description': 'Parking', 'type': 'expense'}, 'taxi': {'categoryId': 'Transport', 'description': 'Taxi/Tuktuk', 'type': 'expense'}, 'movie': {'categoryId': 'Entertainment', 'description': 'Movie', 'type': 'expense'}, 'groceries': {'categoryId': 'Shopping', 'description': 'Groceries', 'type': 'expense'}, 'shopping': {'categoryId': 'Shopping', 'description': 'Shopping', 'type': 'expense'}, 'bills': {'categoryId': 'Bills', 'description': 'Bills', 'type': 'expense'}, 'pizza': {'categoryId': 'Food', 'description': 'Pizza', 'type': 'expense'}, 'others': {'categoryId': 'For Others', 'description': 'For Others', 'type': 'expense'}, 'salary': {'categoryId': 'Salary', 'description': 'Salary', 'type': 'income'}, 'bonus': {'categoryId': 'Bonus', 'description': 'Bonus', 'type': 'income'}, 'commission': {'categoryId': 'Commission', 'description': 'Commission', 'type': 'income'}, 'allowance': {'categoryId': 'Allowance', 'description': 'Allowance', 'type': 'income'}, 'gift': {'categoryId': 'Gift', 'description': 'Gift', 'type': 'income'},
}

def parse_amount_and_currency(amount_str: str):
    amount_str = amount_str.lower()
    if 'khr' in amount_str:
        return float(amount_str.replace('khr', '').strip()), 'KHR'
    else:
        return float(amount_str), 'USD'

def parse_date_from_args(args):
    if not args: return None, args
    try:
        date_str = args[-1]
        parsed_date = datetime.strptime(date_str, '%m-%d')
        today = datetime.now(PHNOM_PENH_TZ)
        tx_datetime = today.replace(month=parsed_date.month, day=parsed_date.day, hour=12, minute=0, second=0, microsecond=0)
        return tx_datetime.isoformat(), args[:-1]
    except (ValueError, TypeError):
        return None, args

# --- NEW HELPER FUNCTION ---
def _format_success_message(data):
    """Formats a detailed success message for logged transactions or debts."""
    lines = ["<b>✅ Recorded:</b>"]

    # Common fields
    lines.append(f"  - <b>Type:</b> {data['type'].title()}")
    amount = data.get('amount') or data.get('iou_amount')
    currency = data.get('currency') or data.get('iou_currency')
    amount_format = ",.0f" if currency == 'KHR' else ",.2f"
    lines.append(f"  - <b>Amount:</b> {amount:{amount_format}} {currency}")

    # Transaction-specific vs Debt-specific
    if 'categoryId' in data:
        lines.append(f"  - <b>Category:</b> {data['categoryId']}")
        if data.get('description'):
            lines.append(f"  - <b>Description:</b> {data['description']}")
    elif 'person' in data:
        lines.append(f"  - <b>Person:</b> {data['person']}")
        if data.get('purpose'):
            lines.append(f"  - <b>Purpose:</b> {data['purpose']}")

    # Date
    if data.get('timestamp'):
        date_obj = datetime.fromisoformat(data['timestamp'])
        date_str = date_obj.strftime('%Y-%m-%d')
        lines.append(f"  - <b>Date:</b> {date_str}")
    else:
        lines.append(f"  - <b>Date:</b> {datetime.now(PHNOM_PENH_TZ).strftime('%Y-%m-%d')}")

    return "\n".join(lines)


# --- Individual Command Logic Functions ---

async def handle_generic_transaction(update: Update, command, args):
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    error_message = f"⚠️ Invalid format. Use:\n`{command} <Category> [\"Description\"] <Amount>[khr] [MM-DD]`"
    try:
        if len(args) < 2:
            await update.message.reply_text(error_message, parse_mode='Markdown')
            return None, None
        args_str_fixed = " ".join(args).replace('“', '"').replace('”', '"')
        parsed_args = shlex.split(args_str_fixed)
        tx_date, remaining_args = parse_date_from_args(parsed_args)
        amount_str = remaining_args[-1]
        amount, currency = parse_amount_and_currency(amount_str)
        category = remaining_args[0]
        description = " ".join(remaining_args[1:-1])
        tx_data = { "type": command, "amount": amount, "currency": currency, "accountName": f"{currency} Account", "categoryId": category, "description": description, "timestamp": tx_date }
        return tx_data, _format_success_message(tx_data)
    except Exception as e:
        logger.error(f"Error parsing generic transaction: {e}", exc_info=True)
        await update.message.reply_text(error_message, parse_mode='Markdown')
        return None, None

async def handle_generic_debt(update: Update, command, args):
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    error_message = f"⚠️ Invalid format. Use:\n`{command} <Person> <Amount>[khr] [\"Purpose\"] [MM-DD]`"
    try:
        if len(args) < 2:
            await update.message.reply_text(error_message, parse_mode='Markdown')
            return None, None
        args_str_fixed = " ".join(args).replace('“', '"').replace('”', '"')
        parsed_args = shlex.split(args_str_fixed)
        tx_date, remaining_args = parse_date_from_args(parsed_args)
        person = remaining_args[0]
        amount_str = remaining_args[1]
        amount, currency = parse_amount_and_currency(amount_str)
        purpose = " ".join(remaining_args[2:])
        debt_data = { "type": command, "person": person, "amount": amount, "currency": currency, "purpose": purpose, "timestamp": tx_date }
        return debt_data, _format_success_message(debt_data)
    except Exception as e:
        logger.error(f"Error parsing generic debt: {e}", exc_info=True)
        await update.message.reply_text(error_message, parse_mode='Markdown')
        return None, None

async def handle_quick_command(update: Update, command, args):
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    try:
        args_str_fixed = " ".join(args).replace('“', '"').replace('”', '"')
        parsed_args = shlex.split(args_str_fixed)

        tx_date, remaining_args = parse_date_from_args(parsed_args)

        if not remaining_args:
            await update.message.reply_text(f"⚠️ Invalid format. Amount is missing.", parse_mode='Markdown')
            return None, None

        amount_str = remaining_args[-1]
        amount, currency = parse_amount_and_currency(amount_str)

        description_parts = remaining_args[:-1]
        details = COMMAND_MAP[command]

        description = " ".join(description_parts) if description_parts else details['description']

        tx_data = {
            "type": details['type'], "amount": amount, "currency": currency,
            "accountName": f"{currency} Account", "categoryId": details['categoryId'],
            "description": description, "timestamp": tx_date
        }
        return tx_data, _format_success_message(tx_data)
    except Exception as e:
        logger.error(f"Error in quick_command_handler: {e}", exc_info=True)
        await update.message.reply_text("An error occurred during quick command processing.")
        return None, None


async def handle_repayment(update: Update, args):
    try:
        if len(args) < 2:
            await update.message.reply_text(f"⚠️ Format: `paid <Person> <Amount> [MM-DD]`", parse_mode='Markdown')
            return

        args_str_fixed = " ".join(args).replace('“', '"').replace('”', '"')
        parsed_args = shlex.split(args_str_fixed)

        tx_date, remaining_args = parse_date_from_args(parsed_args)
        person = remaining_args[0]
        amount_str = remaining_args[1]
        amount, currency = parse_amount_and_currency(amount_str)

        response = api_client.record_lump_sum_repayment(person, currency, amount)
        base_text = response.get('message', '❌ An error occurred.')

    except Exception as e:
        logger.error(f"Error in handle_repayment: {e}", exc_info=True)
        base_text = "⚠️ Invalid format for repayment command."

    summary_text = format_summary_message(api_client.get_detailed_summary())
    await update.message.reply_text(base_text + summary_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())


@restricted
async def repay_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args and args[0].lower() == 'by':
        await handle_repayment(update, args[1:])
    else:
        await handle_repayment(update, args)
    return ConversationHandler.END


# --- Main Message Router ---
@restricted
async def unified_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    full_text = update.message.text
    logger.info(f"--- Message router received text: '{full_text}' ---")

    # --- MODIFICATION START: Add calculator logic ---
    if '=' in full_text:
        expression = full_text.split('=')[0].strip()
        try:
            result = aeval.eval(expression)
            await update.message.reply_text(f"🧮 Result: `{result}`", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Calculator error for expression '{expression}': {e}")
            await update.message.reply_text("Couldn't calculate that. Please check the expression.")
        return ConversationHandler.END
    # --- MODIFICATION END ---

    parts = full_text.split()
    command = parts[0].lower()
    args = parts[1:]

    try:
        if full_text.lower().startswith("repaid by"):
            args = parts[2:]
            await handle_repayment(update, args)
            return ConversationHandler.END

        if command in ["paid", "repaid"]:
            await handle_repayment(update, args)
            return ConversationHandler.END

        tx_data, debt_data, base_text = None, None, None

        if command in ["expense", "income"]:
            tx_data, base_text = await handle_generic_transaction(update, command, args)
        elif command in ["lent", "borrowed"]:
            debt_data, base_text = await handle_generic_debt(update, command, args)
        elif command in COMMAND_MAP:
            tx_data, base_text = await handle_quick_command(update, command, args)
        else:
            context.user_data['unknown_command_data'] = {'command': command, 'args': args}
            return await unknown_command_entry_point(update, context)

        if tx_data:
            response = api_client.add_transaction(tx_data)
            if not response: base_text = "❌ Failed to record transaction."
        elif debt_data:
            response = api_client.add_debt(debt_data)
            if not response: base_text = "❌ Failed to save record."

        if (tx_data or debt_data) and base_text:
            summary_text = format_summary_message(api_client.get_detailed_summary())
            await update.message.reply_text(base_text + summary_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in unified_message_router: {e}", exc_info=True)
        await update.message.reply_text("An error occurred. Please check the format.")
        return ConversationHandler.END

# --- UNKNOWN ITEM CONVERSATION ---
async def unknown_command_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = context.user_data['unknown_command_data']
        command, args = data['command'], data['args']
        tx_date, args_without_date = parse_date_from_args(args)

        if not args_without_date:
            await update.message.reply_text(
                "I'm not sure what you mean. If you're trying to log an expense, please provide an amount (e.g., 'coffee 2.50').")
            return ConversationHandler.END

        amount_str = args_without_date[0]
        amount, currency = parse_amount_and_currency(amount_str)
        context.user_data['new_tx'] = {"type": "expense", "amount": amount, "currency": currency, "accountName": f"{currency} Account", "description": command.replace('_', ' ').title(), "timestamp": tx_date}
        amount_display = f"{amount:,.0f} {currency}" if currency == 'KHR' else f"${amount:,.2f}"
        await update.message.reply_text(f"New expense '{command.title()}' for {amount_display}. Which category?", reply_markup=keyboards.expense_categories_keyboard())
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
    # --- MODIFICATION START: Use detailed success message ---
    base_text = _format_success_message(tx_data) if response else "❌ Failed to record."
    # --- MODIFICATION END ---
    summary_text = format_summary_message(api_client.get_detailed_summary())
    await message.reply_text(base_text + summary_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())
    return ConversationHandler.END

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