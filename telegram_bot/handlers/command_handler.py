# --- Start of new file: telegram_bot/handlers/command_handler.py ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
import api_client
import keyboards
from decorators import restricted
from .helpers import format_summary_message
from datetime import datetime
from zoneinfo import ZoneInfo

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")

# The state for the conversation when a category is needed
SELECT_CATEGORY = range(1)

# Expanded map of known commands for one-step logging
COMMAND_MAP = {
    # Expenses
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
    
    # Incomes
    'salary': {'categoryId': 'Salary', 'description': 'Salary', 'type': 'income'},
    'bonus': {'categoryId': 'Bonus', 'description': 'Bonus', 'type': 'income'},
    'commission': {'categoryId': 'Commission', 'description': 'Commission', 'type': 'income'},
    'allowance': {'categoryId': 'Allowance', 'description': 'Allowance', 'type': 'income'},
    'gift': {'categoryId': 'Gift', 'description': 'Gift', 'type': 'income'},
}

def parse_amount_and_currency(amount_str: str):
    """Parses a string like '5000khr' or '2.5' into amount and currency."""
    amount_str = amount_str.lower()
    if 'khr' in amount_str:
        currency = 'KHR'
        amount = float(amount_str.replace('khr', '').strip())
    else:
        currency = 'USD'
        amount = float(amount_str)
    return amount, currency

@restricted
async def command_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles all commands. If the command is known, logs it instantly.
    If unknown, it asks for a category, starting a short conversation.
    """
    try:
        command = update.message.text.split()[0][1:].lower()
        args = context.args

        if not args:
            await update.message.reply_text(f"⚠️ Please provide an amount.\nExample: `/{command} 5.50`", parse_mode='Markdown')
            return ConversationHandler.END

        # --- Parse amount and optional date (MM-DD) ---
        tx_date = None
        amount_str = args[0]
        if len(args) > 1:
            try:
                date_str = args[1]
                parsed_date = datetime.strptime(date_str, '%m-%d')
                today = datetime.now(PHNOM_PENH_TZ)
                tx_date = today.replace(month=parsed_date.month, day=parsed_date.day, hour=12, minute=0, second=0, microsecond=0).isoformat()
            except (ValueError, TypeError):
                await update.message.reply_text(f"⚠️ Invalid date format. Please use `MM-DD`.", parse_mode='Markdown')
                return ConversationHandler.END
        
        amount, currency = parse_amount_and_currency(amount_str)

        # --- Logic for KNOWN vs UNKNOWN commands ---
        if command in COMMAND_MAP:
            # KNOWN command: Log it directly
            details = COMMAND_MAP[command]
            tx_data = {
                "type": details['type'],
                "amount": amount,
                "currency": currency,
                "accountName": f"{currency} Account",
                "categoryId": details['categoryId'],
                "description": details['description'],
                "timestamp": tx_date
            }
            response = api_client.add_transaction(tx_data)
            base_text = "✅ Quick transaction recorded!" if response else "❌ Failed to record transaction."
            summary_text = format_summary_message(api_client.get_detailed_summary())
            await update.message.reply_text(base_text + summary_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())
            return ConversationHandler.END
        else:
            # UNKNOWN command: Treat as new expense and ask for category
            context.user_data['new_tx'] = {
                "type": "expense",
                "amount": amount,
                "currency": currency,
                "accountName": f"{currency} Account",
                "description": command.replace('_', ' ').title(),
                "timestamp": tx_date
            }
            amount_display = f"{amount:,.0f} {currency}" if currency == 'KHR' else f"${amount:,.2f} {currency}"
            await update.message.reply_text(
                f"New expense '{command.title()}' for {amount_display}. Which category does this belong to?",
                reply_markup=keyboards.expense_categories_keyboard()
            )
            return SELECT_CATEGORY

    except (IndexError, ValueError):
        command_name = update.message.text.split()[0][1:].lower()
        await update.message.reply_text(f"⚠️ Invalid amount or format. Use `/{command_name} <amount> [MM-DD]`", parse_mode='Markdown')
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")
        return ConversationHandler.END

@restricted
async def received_category_for_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receives the category for a new command-based transaction and saves it.
    """
    query = update.callback_query
    await query.answer()

    category = query.data.split('_')[1]
    
    tx_data = context.user_data.get('new_tx')
    if not tx_data:
        await query.edit_message_text("Sorry, something went wrong. Please start over.", reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END

    if category == 'other':
        await query.edit_message_text("Sorry, creating a custom category via commands is not supported. Please choose a pre-defined one or use the 'Add Expense' button.")
        return SELECT_CATEGORY # Stay in the same state

    tx_data['categoryId'] = category

    response = api_client.add_transaction(tx_data)
    base_text = "✅ New transaction recorded!" if response else "❌ Failed to record transaction."
    summary_text = format_summary_message(api_client.get_detailed_summary())
    await query.edit_message_text(base_text + summary_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())
    
    context.user_data.clear()
    return ConversationHandler.END

# Build the unified command handler
unified_command_conversation_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.COMMAND, command_entry_point)],
    states={
        SELECT_CATEGORY: [CallbackQueryHandler(received_category_for_unknown_command, pattern='^cat_')]
    },
    fallbacks=[CallbackQueryHandler(keyboards.main_menu_keyboard, pattern='^start$')],
    per_message=False
)
