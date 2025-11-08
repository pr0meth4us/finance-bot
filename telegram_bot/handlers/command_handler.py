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
# NOTE: You must add 'asteval' to your requirements.txt
from asteval import Interpreter

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
SELECT_CATEGORY, GET_CUSTOM_CATEGORY = range(2)
aeval = Interpreter()

COMMAND_MAP = {
    'coffee': {'categoryId': 'Drink', 'description': 'Coffee', 'type': 'expense'}, 'lunch': {'categoryId': 'Food', 'description': 'Lunch', 'type': 'expense'}, 'dinner': {'categoryId': 'Food', 'description': 'Dinner', 'type': 'expense'}, 'gas': {'categoryId': 'Transport', 'description': 'Gas', 'type': 'expense'}, 'parking': {'categoryId': 'Transport', 'description': 'Parking', 'type': 'expense'}, 'taxi': {'categoryId': 'Transport', 'description': 'Taxi/Tuktuk', 'type': 'expense'}, 'movie': {'categoryId': 'Entertainment', 'description': 'Movie', 'type': 'expense'}, 'groceries': {'categoryId': 'Shopping', 'description': 'Groceries', 'type': 'expense'}, 'shopping': {'categoryId': 'Shopping', 'description': 'Shopping', 'type': 'expense'}, 'bills': {'categoryId': 'Bills', 'description': 'Bills', 'type': 'expense'}, 'pizza': {'categoryId': 'Food', 'description': 'Pizza', 'type': 'expense'}, 'others': {'categoryId': 'For Others', 'description': 'For Others', 'type': 'expense'},
    'alcohol': {'categoryId': 'Alcohol', 'description': 'Alcohol', 'type': 'expense'},
    'investment': {'categoryId': 'Investment', 'description': 'Investment', 'type': 'expense'}, # <-- NEW
    'salary': {'categoryId': 'Salary', 'description': 'Salary', 'type': 'income'}, 'bonus': {'categoryId': 'Bonus', 'description': 'Bonus', 'type': 'income'}, 'commission': {'categoryId': 'Commission', 'description': 'Commission', 'type': 'income'}, 'allowance': {'categoryId': 'Allowance', 'description': 'Allowance', 'type': 'income'}, 'gift': {'categoryId': 'Gift', 'description': 'Gift', 'type': 'income'},
}

def parse_amount_and_currency(amount_str: str):
    amount_str = amount_str.lower()
    if 'khr' in amount_str:
        return float(amount_str.replace('khr', '').strip()), 'KHR'
    else:
        return float(amount_str), 'USD'

def parse_date_from_args(args):
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    if not args: return None, args

    date_str = args[-1]
    parsed_date = None
    today = datetime.now(PHNOM_PENH_TZ)

    try:
        # Try MM-DD format first
        parsed_date = datetime.strptime(date_str, '%m-%d')
    except (ValueError, TypeError):
        try:
            # Try DD-MM format next
            parsed_date = datetime.strptime(date_str, '%d-%m')
        except (ValueError, TypeError):
            # Not a valid date, return original args
            return None, args

    # If parsing succeeded
    tx_datetime = today.replace(month=parsed_date.month, day=parsed_date.day, hour=12, minute=0, second=0, microsecond=0)
    return tx_datetime.isoformat(), args[:-1]

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
    # --- FIX: Updated error message format to include ! prefix ---
    error_message = f"⚠️ Invalid format.\n`!{command} <Category> [\"Description\"] <Amount>[khr] [MM-DD]`\n\n(Tip: Use quotes for multi-word descriptions)"
    try:
        if len(args) < 2:
            await update.message.reply_text(error_message, parse_mode='Markdown')
            return None, None

        # --- FIX: Removed shlex.split, as args are now pre-parsed by the router ---
        parsed_args = args

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
    # --- FIX: Updated error message format to include ! prefix ---
    error_message = f"⚠️ Invalid format.\n`!{command} <Person> <Amount>[khr] [\"Purpose\"] [MM-DD]`\n\n(Tip: Use quotes for multi-word names or purposes)"
    try:
        if len(args) < 2:
            await update.message.reply_text(error_message, parse_mode='Markdown')
            return None, None

        # --- FIX: Removed shlex.split, as args are now pre-parsed by the router ---
        parsed_args = args

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
        # --- FIX: Removed shlex.split, as args are now pre-parsed by the router ---
        parsed_args = args

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


async def handle_repayment(update: Update, args, debt_type: str):
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    try:
        # --- FIX: Updated error message format to include ! prefix ---
        command_example = "`!repaid by <Person> <Amount>[khr] [MM-DD]`" if debt_type == 'lent' else "`!paid <Person> <Amount>[khr] [MM-DD]`"

        # --- FIX: Removed shlex.split, as args are now pre-parsed by the router ---
        parsed_args = args

        tx_date, remaining_args = parse_date_from_args(parsed_args)

        if len(remaining_args) < 2:
            await update.message.reply_text(f"⚠️ Format: {command_example}", parse_mode='Markdown')
            return

        person = remaining_args[0]
        amount_str = remaining_args[1]
        amount, currency = parse_amount_and_currency(amount_str)

        # --- FIX: Pass tx_date (which can be None) to the API client ---
        response = api_client.record_lump_sum_repayment(person, currency, amount, debt_type, tx_date)
        base_text = response.get('message', '❌ An error occurred.')
        if response.get('error'):
            base_text = f"❌ Error: {response.get('error')}"

    except Exception as e:
        logger.error(f"Error in handle_repayment: {e}", exc_info=True)
        base_text = "⚠️ Invalid format for repayment command."

    summary_text = format_summary_message(api_client.get_detailed_summary())
    await update.message.reply_text(base_text + summary_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())


# --- Main Message Router ---
@restricted
async def unified_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    full_text = update.message.text
    logger.info(f"--- Message router received text: '{full_text}' ---")

    # --- FIX: Check for ! prefix ---
    if not full_text.startswith('!'):
        # If no prefix, check for calculator, otherwise ignore
        if '=' in full_text:
            expression = full_text.split('=')[0].strip()
            try:
                result = aeval.eval(expression)
                await update.message.reply_text(f"🧮 Result: `{result}`", parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Calculator error for expression '{expression}': {e}")
                await update.message.reply_text("Couldn't calculate that. Please check the expression.")
        else:
            logger.info("Ignoring message, no '!' prefix or '=' found.")
        return ConversationHandler.END

    # --- FIX: Strip prefix and parse with shlex ---
    full_text = full_text[1:].strip() # Get text after !
    # Fix smart quotes and single quotes
    full_text_fixed = full_text.replace('“', '"').replace('”', '"').replace("‘", "'").replace("’", "'")

    try:
        parts = shlex.split(full_text_fixed)
    except ValueError as e:
        logger.warning(f"Shlex parsing error: {e}. Likely an unclosed quote.")
        await update.message.reply_text(f"⚠️ Parsing error. Check your quotes: {e}")
        return ConversationHandler.END

    if not parts:
        return ConversationHandler.END # Just an "!" was sent

    command = parts[0].lower()
    args = parts[1:]
    # --- End Fix ---

    try:
        # --- FIX: Reroute repayment commands (must check full_text, not parts) ---
        if full_text.lower().startswith("repaid by") or full_text.lower().startswith("paid by"):
            args = parts[2:] # Get args after "repaid by" or "paid by"
            await handle_repayment(update, args, debt_type='lent') # 'lent' = someone is paying me
            return ConversationHandler.END

        if command in ["paid", "repaid"]:
            await handle_repayment(update, args, debt_type='borrowed') # 'borrowed' = I am paying someone
            return ConversationHandler.END
        # --- End Fix ---

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
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    try:
        data = context.user_data['unknown_command_data']
        command, args = data['command'], data['args']
        tx_date, args_without_date = parse_date_from_args(args)

        if not args_without_date:
            await update.message.reply_text(
                "I'm not sure what you mean. If you're trying to log an expense, please provide an amount (e.g., '!coffee 2.50').")
            return ConversationHandler.END

        # --- FIX: Amount is the LAST arg, description is everything before it ---
        amount_str = args_without_date[-1]
        description_parts = args_without_date[:-1]

        try:
            amount, currency = parse_amount_and_currency(amount_str)
        except ValueError:
            await update.message.reply_text(
                "I'm not sure what you mean. Please provide an amount (e.g., '!coffee 2.50').")
            return ConversationHandler.END

        # Combine command and description parts
        description = command.replace('_', ' ').title()
        if description_parts:
            description += f" {' '.join(description_parts)}"

        context.user_data['new_tx'] = {
            "type": "expense", "amount": amount, "currency": currency,
            "accountName": f"{currency} Account", "description": description,
            "timestamp": tx_date
        }

        amount_display = f"{amount:,.0f} {currency}" if currency == 'KHR' else f"${amount:,.2f}"

        # --- FIX: Use the full 'description' in the reply, not just 'command.title()' ---
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
    base_text = _format_success_message(tx_data) if response else "❌ Failed to record."
    summary_text = format_summary_message(api_client.get_detailed_summary())
    await message.reply_text(base_text + summary_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())
    return ConversationHandler.END

unified_message_conversation_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, unified_message_router)],
    states={
        SELECT_CATEGORY: [CallbackQueryHandler(received_category_for_unknown, pattern='^cat_')],
        GET_CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_text_for_custom_category)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start), CallbackQueryHandler(start, pattern='^start$')],
    per_message=False,
    conversation_timeout=60
)