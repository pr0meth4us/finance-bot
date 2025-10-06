# --- Start of new file: telegram_bot/handlers/generic_commands.py ---

from telegram import Update
from telegram.ext import ContextTypes
import api_client
import keyboards
from decorators import restricted
from .helpers import format_summary_message
from datetime import datetime
from zoneinfo import ZoneInfo

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")

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

def parse_date_from_args(args):
    """Checks the last argument for a date (MM-DD) and returns it, or None."""
    if not args:
        return None, args

    try:
        date_str = args[-1]
        parsed_date = datetime.strptime(date_str, '%m-%d')
        today = datetime.now(PHNOM_PENH_TZ)
        # Assume current year, set time to midday
        tx_datetime = today.replace(
            month=parsed_date.month, day=parsed_date.day, 
            hour=12, minute=0, second=0, microsecond=0
        )
        return tx_datetime.isoformat(), args[:-1] # Return date and remaining args
    except (ValueError, TypeError):
        return None, args

@restricted
async def generic_transaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles generic /expense and /income commands."""
    command = "command"
    try:
        command = update.message.text.split()[0][1:].lower()
        args = context.args
        
        if len(args) < 3:
            await update.message.reply_text(f"⚠️ Invalid format. Use:\n`/{command} <Category> <Description> <Amount> [MM-DD]`", parse_mode='Markdown')
            return

        tx_date, remaining_args = parse_date_from_args(args)
        
        amount_str = remaining_args[-1]
        amount, currency = parse_amount_and_currency(amount_str)
        
        category = remaining_args[0]
        description = " ".join(remaining_args[1:-1])

        tx_data = {
            "type": command,
            "amount": amount,
            "currency": currency,
            "accountName": f"{currency} Account",
            "categoryId": category,
            "description": description,
            "timestamp": tx_date
        }

        response = api_client.add_transaction(tx_data)
        base_text = f"✅ Generic {command} recorded!" if response else f"❌ Failed to record {command}."
        summary_text = format_summary_message(api_client.get_detailed_summary())
        await update.message.reply_text(base_text + summary_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())

    except (ValueError, IndexError):
        await update.message.reply_text(f"⚠️ Invalid format. Use:\n`/{command} <Category> <Description> <Amount> [MM-DD]`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")


@restricted
async def generic_debt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles generic /lent and /borrowed commands."""
    command = "command"
    try:
        command = update.message.text.split()[0][1:].lower()
        args = context.args

        if len(args) < 3:
            await update.message.reply_text(f"⚠️ Invalid format. Use:\n`/{command} <Person> <Amount> <Purpose> [MM-DD]`", parse_mode='Markdown')
            return
        
        tx_date, remaining_args = parse_date_from_args(args)

        person = remaining_args[0]
        amount_str = remaining_args[1]
        amount, currency = parse_amount_and_currency(amount_str)
        purpose = " ".join(remaining_args[2:])

        debt_data = {
            "type": command,
            "person": person,
            "amount": amount,
            "currency": currency,
            "purpose": purpose,
            "timestamp": tx_date
        }

        response = api_client.add_debt(debt_data)
        base_text = f"✅ {command.title()} record saved!" if response else f"❌ Failed to save {command} record."
        summary_text = format_summary_message(api_client.get_detailed_summary())
        await update.message.reply_text(base_text + summary_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())

    except (ValueError, IndexError):
         await update.message.reply_text(f"⚠️ Invalid format. Use:\n`/{command} <Person> <Amount> <Purpose> [MM-DD]`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")
