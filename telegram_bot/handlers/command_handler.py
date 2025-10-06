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

SELECT_CATEGORY = range(1)

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
    'salary': {'categoryId': 'Salary', 'description': 'Salary', 'type': 'income'},
    'bonus': {'categoryId': 'Bonus', 'description': 'Bonus', 'type': 'income'},
    'commission': {'categoryId': 'Commission', 'description': 'Commission', 'type': 'income'},
    'allowance': {'categoryId': 'Allowance', 'description': 'Allowance', 'type': 'income'},
    'gift': {'categoryId': 'Gift', 'description': 'Gift', 'type': 'income'},
}


def parse_amount_and_currency(amount_str: str):
    amount_str = amount_str.lower()
    if 'khr' in amount_str:
        currency = 'KHR'
        amount = float(amount_str.replace('khr', '').strip())
    else:
        currency = 'USD'
        amount = float(amount_str)
    return amount, currency


def parse_date_from_args(args):
    if not args: return None, args
    try:
        date_str = args[-1]
        parsed_date = datetime.strptime(date_str, '%m-%d')
        today = datetime.now(PHNOM_PENH_TZ)
        tx_datetime = today.replace(month=parsed_date.month, day=parsed_date.day, hour=12, minute=0, second=0,
                                    microsecond=0)
        return tx_datetime.isoformat(), args[:-1]
    except (ValueError, TypeError):
        return None, args


@restricted
async def command_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        command = update.message.text.split()[0][1:].lower()
        args = context.args

        # --- Generic Commands ---
        if command in ["expense", "income"]:
            if len(args) < 3:
                await update.message.reply_text(
                    f"⚠️ Invalid format. Use:\n`/{command} <Category> <Description> <Amount> [MM-DD]`",
                    parse_mode='Markdown')
                return ConversationHandler.END

            tx_date, remaining_args = parse_date_from_args(args)
            amount_str = remaining_args[-1]
            amount, currency = parse_amount_and_currency(amount_str)
            category = remaining_args[0]
            description = " ".join(remaining_args[1:-1])
            tx_data = {"type": command, "amount": amount, "currency": currency, "accountName": f"{currency} Account",
                       "categoryId": category, "description": description, "timestamp": tx_date}

            response = api_client.add_transaction(tx_data)
            base_text = f"✅ Generic {command} recorded!" if response else f"❌ Failed to record {command}."
            summary_text = format_summary_message(api_client.get_detailed_summary())
            await update.message.reply_text(base_text + summary_text, parse_mode='HTML',
                                            reply_markup=keyboards.main_menu_keyboard())
            return ConversationHandler.END

        if command in ["lent", "borrowed"]:
            if len(args) < 3:
                await update.message.reply_text(
                    f"⚠️ Invalid format. Use:\n`/{command} <Person> <Amount> <Purpose> [MM-DD]`", parse_mode='Markdown')
                return ConversationHandler.END

            tx_date, remaining_args = parse_date_from_args(args)
            person = remaining_args[0]
            amount_str = remaining_args[1]
            amount, currency = parse_amount_and_currency(amount_str)
            purpose = " ".join(remaining_args[2:])
            debt_data = {"type": command, "person": person, "amount": amount, "currency": currency, "purpose": purpose,
                         "timestamp": tx_date}

            response = api_client.add_debt(debt_data)
            base_text = f"✅ {command.title()} record saved!" if response else f"❌ Failed to save {command} record."
            summary_text = format_summary_message(api_client.get_detailed_summary())
            await update.message.reply_text(base_text + summary_text, parse_mode='HTML',
                                            reply_markup=keyboards.main_menu_keyboard())
            return ConversationHandler.END

        # --- Smart Quick Commands (Known and Unknown) ---
        if not args:
            await update.message.reply_text(f"⚠️ Please provide an amount.\nExample: `/{command} 5.50`",
                                            parse_mode='Markdown')
            return ConversationHandler.END

        tx_date, remaining_args = parse_date_from_args(args)
        amount_str = remaining_args[0]
        amount, currency = parse_amount_and_currency(amount_str)

        if command in COMMAND_MAP:
            details = COMMAND_MAP[command]
            tx_data = {"type": details['type'], "amount": amount, "currency": currency,
                       "accountName": f"{currency} Account", "categoryId": details['categoryId'],
                       "description": details['description'], "timestamp": tx_date}
            response = api_client.add_transaction(tx_data)
            base_text = "✅ Quick transaction recorded!" if response else "❌ Failed to record."
            summary_text = format_summary_message(api_client.get_detailed_summary())
            await update.message.reply_text(base_text + summary_text, parse_mode='HTML',
                                            reply_markup=keyboards.main_menu_keyboard())
            return ConversationHandler.END
        else:
            context.user_data['new_tx'] = {"type": "expense", "amount": amount, "currency": currency,
                                           "accountName": f"{currency} Account",
                                           "description": command.replace('_', ' ').title(), "timestamp": tx_date}
            amount_display = f"{amount:,.0f} {currency}" if currency == 'KHR' else f"${amount:,.2f}"
            await update.message.reply_text(f"New expense '{command.title()}' for {amount_display}. Which category?",
                                            reply_markup=keyboards.expense_categories_keyboard())
            return SELECT_CATEGORY

    except (IndexError, ValueError):
        await update.message.reply_text(f"⚠️ Invalid format for that command.", parse_mode='Markdown')
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")
        return ConversationHandler.END


@restricted
async def received_category_for_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split('_')[1]
    tx_data = context.user_data.get('new_tx')

    if not tx_data:
        await query.edit_message_text("Sorry, something went wrong. Please start over.",
                                      reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END

    if category == 'other':
        await query.edit_message_text(
            "Custom categories via commands are not supported. Please choose a pre-defined one or use the 'Add Expense' button.",
            reply_markup=keyboards.expense_categories_keyboard())
        return SELECT_CATEGORY

    tx_data['categoryId'] = category
    response = api_client.add_transaction(tx_data)
    base_text = "✅ New transaction recorded!" if response else "❌ Failed to record."
    summary_text = format_summary_message(api_client.get_detailed_summary())
    await query.edit_message_text(base_text + summary_text, parse_mode='HTML',
                                  reply_markup=keyboards.main_menu_keyboard())

    context.user_data.clear()
    return ConversationHandler.END


unified_command_conversation_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.COMMAND, command_entry_point)],
    states={
        SELECT_CATEGORY: [CallbackQueryHandler(received_category_for_unknown_command, pattern='^cat_')]
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)