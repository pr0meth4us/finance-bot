# --- Start of new file: telegram_bot/handlers/quick_commands.py ---

from telegram import Update
from telegram.ext import ContextTypes
import api_client
import keyboards
from decorators import restricted
from .helpers import format_summary_message
from datetime import datetime
from zoneinfo import ZoneInfo

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")

COMMAND_MAP = {
    # Expenses
    'coffee': {'categoryId': 'Drink', 'description': 'Coffee', 'type': 'expense'},
    'lunch': {'categoryId': 'Food', 'description': 'Lunch', 'type': 'expense'},
    'dinner': {'categoryId': 'Food', 'description': 'Dinner', 'type': 'expense'},
    'gas': {'categoryId': 'Transport', 'description': 'Gas', 'type': 'expense'},
    'parking': {'categoryId': 'Transport', 'description': 'Parking', 'type': 'expense'},
    'movie': {'categoryId': 'Entertainment', 'description': 'Movie', 'type': 'expense'},
    'pizza': {'categoryId': 'Food', 'description': 'Pizza', 'type': 'expense'},
    'nuggets': {'categoryId': 'Food', 'description': 'Nuggets', 'type': 'expense'},
    'groceries': {'categoryId': 'Shopping', 'description': 'Groceries', 'type': 'expense'},
    # Incomes
    'salary': {'categoryId': 'Salary', 'description': 'Salary', 'type': 'income'},
    'bonus': {'categoryId': 'Bonus', 'description': 'Bonus', 'type': 'income'},
    'allowance': {'categoryId': 'Allowance', 'description': 'Allowance', 'type': 'income'},
}

@restricted
async def quick_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles quick commands like /coffee 1.5 or /coffee 1.5 09-28"""
    command_name = "command"
    try:
        command_with_slash = update.message.text.split()[0]
        command = command_with_slash[1:].lower()
        command_name = command

        if not context.args:
            await update.message.reply_text(f"⚠️ Please provide an amount.\nExample: `/{command} 1.5`", parse_mode='Markdown')
            return

        # --- Date parsing logic ---
        args = context.args
        tx_date = None
        amount_str = args[0]

        if len(args) > 1:
            try:
                date_str = args[1]
                parsed_date = datetime.strptime(date_str, '%m-%d')
                today = datetime.now(PHNOM_PENH_TZ)
                tx_date = today.replace(
                    month=parsed_date.month, day=parsed_date.day,
                    hour=12, minute=0, second=0, microsecond=0
                ).isoformat()
            except (ValueError, TypeError):
                # If the second argument isn't a valid date, show an error
                await update.message.reply_text(f"⚠️ Invalid date format. Please use `MM-DD`.", parse_mode='Markdown')
                return
        
        amount = float(amount_str)

        if command not in COMMAND_MAP:
            return

        details = COMMAND_MAP[command]
        
        tx_data = {
            "type": details['type'],
            "amount": amount,
            "currency": "USD",
            "accountName": "USD Account",
            "categoryId": details['categoryId'],
            "description": details['description'],
            "timestamp": tx_date
        }

        response = api_client.add_transaction(tx_data)
        
        base_text = "✅ Quick transaction recorded!" if response else "❌ Failed to record transaction."
        summary_text = format_summary_message(api_client.get_detailed_summary())
        await update.message.reply_text(
            base_text + summary_text, 
            parse_mode='HTML', 
            reply_markup=keyboards.main_menu_keyboard()
        )

    except (IndexError, ValueError):
        await update.message.reply_text(f"⚠️ Invalid format. Use `/{command_name} <amount> [MM-DD]`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")
