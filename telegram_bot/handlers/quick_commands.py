# --- Start of new file: telegram_bot/handlers/quick_commands.py ---

from telegram import Update
from telegram.ext import ContextTypes
import api_client
import keyboards
from decorators import restricted
from .helpers import format_summary_message

COMMAND_MAP = {
    'coffee': {'categoryId': 'Drink', 'description': 'Coffee'},
    'lunch': {'categoryId': 'Food', 'description': 'Lunch'},
    'dinner': {'categoryId': 'Food', 'description': 'Dinner'},
    'gas': {'categoryId': 'Transport', 'description': 'Gas'},
}


@restricted
async def quick_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles quick commands like /coffee 1.5"""
    try:
        command = context.command.lower()

        if not context.args:
            await update.message.reply_text(
                f"⚠️ Please provide an amount. Use: /{command} <amount>\nExample: /{command} 1.5"
            )
            return

        amount_str = context.args[0]
        amount = float(amount_str)

        if command not in COMMAND_MAP:
            return

        details = COMMAND_MAP[command]

        tx_data = {
            "type": "expense",
            "amount": amount,
            "currency": "USD",  # Assume USD for all quick commands
            "accountName": "USD Account",
            "categoryId": details['categoryId'],
            "description": details['description']
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
        await update.message.reply_text(
            f"⚠️ Invalid format. Use: /{context.command} <amount>\nExample: /{context.command} 1.5"
        )
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")