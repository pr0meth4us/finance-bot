# --- Start of modified file: telegram_bot/handlers/command_handler.py ---

from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters, CommandHandler
)
import api_client
import keyboards
from decorators import authenticate_user
from .helpers import format_summary_message
from .common import cancel, start
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import shlex
from asteval import Interpreter
from ..utils.i18n import t

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
SELECT_CATEGORY, GET_CUSTOM_CATEGORY = range(2)
aeval = Interpreter()

COMMAND_MAP = {
    'coffee': {'categoryId': 'Drink', 'description': 'Coffee',
               'type': 'expense'},
    'lunch': {'categoryId': 'Food', 'description': 'Lunch',
              'type': 'expense'},
    'dinner': {'categoryId': 'Food', 'description': 'Dinner',
               'type': 'expense'},
    'gas': {'categoryId': 'Transport', 'description': 'Gas',
            'type': 'expense'},
    'parking': {'categoryId': 'Transport', 'description': 'Parking',
                'type': 'expense'},
    'taxi': {'categoryId': 'Transport', 'description': 'Taxi/Tuktuk',
             'type': 'expense'},
    'movie': {'categoryId': 'Entertainment', 'description': 'Movie',
              'type': 'expense'},
    'groceries': {'categoryId': 'Shopping', 'description': 'Groceries',
                  'type': 'expense'},
    'shopping': {'categoryId': 'Shopping', 'description': 'Shopping',
                 'type': 'expense'},
    'bills': {'categoryId': 'Bills', 'description': 'Bills',
              'type': 'expense'},
    'pizza': {'categoryId': 'Food', 'description': 'Pizza',
              'type': 'expense'},
    'others': {'categoryId': 'For Others', 'description': 'For Others',
               'type': 'expense'},
    'alcohol': {'categoryId': 'Alcohol', 'description': 'Alcohol',
                'type': 'expense'},
    'investment': {'categoryId': 'Investment', 'description': 'Investment',
                   'type': 'expense'},
    'salary': {'categoryId': 'Salary', 'description': 'Salary',
               'type': 'income'},
    'bonus': {'categoryId': 'Bonus', 'description': 'Bonus',
              'type': 'income'},
    'commission': {'categoryId': 'Commission', 'description': 'Commission',
                   'type': 'income'},
    'allowance': {'categoryId': 'Allowance', 'description': 'Allowance',
                  'type': 'income'},
    'gift': {'categoryId': 'Gift', 'description': 'Gift',
             'type': 'income'},
}


def parse_amount_and_currency(amount_str: str):
    amount_str = amount_str.lower()
    if 'khr' in amount_str:
        return float(amount_str.replace('khr', '').strip()), 'KHR'

    return float(amount_str), 'USD'


def parse_date_from_args(args):
    if not args:
        return None, args

    date_str = args[-1]
    parsed_date = None
    today = datetime.now(PHNOM_PENH_TZ)

    try:
        parsed_date = datetime.strptime(date_str, '%m-%d')
    except (ValueError, TypeError):
        try:
            parsed_date = datetime.strptime(date_str, '%d-%m')
        except (ValueError, TypeError):
            return None, args

    tx_datetime = today.replace(
        month=parsed_date.month, day=parsed_date.day,
        hour=12, minute=0, second=0, microsecond=0
    )
    return tx_datetime.isoformat(), args[:-1]


def _format_success_message(data):
    """Formats a detailed success message for logged items."""
    lines = ["<b>✅ Recorded:</b>"]
    lines.append(f"  - <b>Type:</b> {data['type'].title()}")
    amount = data.get('amount') or data.get('iou_amount')
    currency = data.get('currency') or data.get('iou_currency')
    amount_format = ",.0f" if currency == 'KHR' else ",.2f"
    lines.append(f"  - <b>Amount:</b> {amount:{amount_format}} {currency}")

    if 'categoryId' in data:
        lines.append(f"  - <b>Category:</b> {data['categoryId']}")
        if data.get('description'):
            lines.append(f"  - <b>Description:</b> {data['description']}")
    elif 'person' in data:
        lines.append(f"  - <b>Person:</b> {data['person']}")
        if data.get('purpose'):
            lines.append(f"  - <b>Purpose:</b> {data['purpose']}")

    if data.get('timestamp'):
        date_obj = datetime.fromisoformat(data['timestamp'])
        date_str = date_obj.strftime('%Y-%m-%d')
        lines.append(f"  - <b>Date:</b> {date_str}")
    else:
        lines.append(
            f"  - <b>Date:</b> {datetime.now(PHNOM_PENH_TZ).strftime('%Y-%m-%d')}"
        )

    return "\n".join(lines)


async def handle_generic_transaction(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE,
                                     command, args):
    """Handles parsing !expense and !income commands."""
    error_message = t("command.invalid_format_generic", context, command=command)
    try:
        if len(args) < 2:
            await update.message.reply_text(error_message, parse_mode='Markdown')
            return None, None

        parsed_args = args
        tx_date, remaining_args = parse_date_from_args(parsed_args)
        amount_str = remaining_args[-1]
        amount, currency = parse_amount_and_currency(amount_str)
        category = remaining_args[0]
        description = " ".join(remaining_args[1:-1])
        tx_data = {
            "type": command, "amount": amount, "currency": currency,
            "accountName": f"{currency} Account", "categoryId": category,
            "description": description, "timestamp": tx_date
        }
        return tx_data, _format_success_message(tx_data)
    except Exception as e:
        logger.error(f"Error parsing generic transaction: {e}", exc_info=True)
        await update.message.reply_text(error_message, parse_mode='Markdown')
        return None, None


async def handle_generic_debt(update: Update,
                              context: ContextTypes.DEFAULT_TYPE,
                              command, args):
    """Handles parsing !lent and !borrowed commands."""
    error_message = t("command.invalid_format_debt", context, command=command)
    try:
        if len(args) < 2:
            await update.message.reply_text(error_message, parse_mode='Markdown')
            return None, None

        parsed_args = args
        tx_date, remaining_args = parse_date_from_args(parsed_args)
        person = remaining_args[0]
        amount_str = remaining_args[1]
        amount, currency = parse_amount_and_currency(amount_str)
        purpose = " ".join(remaining_args[2:])
        debt_data = {
            "type": command, "person": person, "amount": amount,
            "currency": currency, "purpose": purpose, "timestamp": tx_date
        }
        return debt_data, _format_success_message(debt_data)
    except Exception as e:
        logger.error(f"Error parsing generic debt: {e}", exc_info=True)
        await update.message.reply_text(error_message, parse_mode='Markdown')
        return None, None


async def handle_quick_command(update: Update,
                               context: ContextTypes.DEFAULT_TYPE,
                               command, args):
    """Handles parsing predefined quick commands like !coffee."""
    try:
        parsed_args = args
        tx_date, remaining_args = parse_date_from_args(parsed_args)

        if not remaining_args:
            await update.message.reply_text(
                t("command.invalid_format_missing_amount", context),
                parse_mode='Markdown'
            )
            return None, None

        amount_str = remaining_args[-1]
        amount, currency = parse_amount_and_currency(amount_str)
        description_parts = remaining_args[:-1]
        details = COMMAND_MAP[command]
        description = (" ".join(description_parts) if description_parts
                       else details['description'])

        tx_data = {
            "type": details['type'], "amount": amount, "currency": currency,
            "accountName": f"{currency} Account",
            "categoryId": details['categoryId'],
            "description": description, "timestamp": tx_date
        }
        return tx_data, _format_success_message(tx_data)
    except Exception as e:
        logger.error(f"Error in quick_command_handler: {e}", exc_info=True)
        await update.message.reply_text(
            t("command.error_generic", context)
        )
        return None, None


async def handle_repayment(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           args, debt_type: str):
    """Handles parsing !paid and !repaid by commands."""
    try:
        user_id = context.user_data['user_profile']['_id']

        command_example = (
            "`!repaid by <Person> <Amount>[khr] [MM-DD]`"
            if debt_type == 'lent'
            else "`!paid <Person> <Amount>[khr] [MM-DD]`"
        )
        parsed_args = args
        tx_date, remaining_args = parse_date_from_args(parsed_args)

        if len(remaining_args) < 2:
            await update.message.reply_text(
                t("command.invalid_format_repayment",
                  context, example=command_example),
                parse_mode='Markdown'
            )
            return

        person = remaining_args[0]
        amount_str = remaining_args[1]
        amount, currency = parse_amount_and_currency(amount_str)

        response = api_client.record_lump_sum_repayment(
            person, currency, amount, debt_type, user_id, tx_date
        )
        base_text = response.get('message', '❌ An error occurred.')
        if response.get('error'):
            base_text = t("command.repayment_error",
                          context, error=response.get('error'))

    except Exception as e:
        logger.error(f"Error in handle_repayment: {e}", exc_info=True)
        base_text = t("command.repayment_fail", context)

    summary_text = format_summary_message(
        api_client.get_detailed_summary(user_id), context
    )
    await update.message.reply_text(
        base_text + summary_text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard(context)
    )


@authenticate_user
async def unified_message_router(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    """The main router for all text messages, now authenticated."""
    full_text = update.message.text
    logger.info(f"--- Message router received text: '{full_text}' ---")

    if not full_text.startswith('!'):
        if '=' in full_text:
            expression = full_text.split('=')[0].strip()
            try:
                result = aeval.eval(expression)
                await update.message.reply_text(
                    t("command.calculating", context, result=result),
                    parse_mode='Markdown'
                )
            except Exception:
                logger.error(f"Calculator error for '{expression}'")
                await update.message.reply_text(
                    t("command.calculator_fail", context)
                )
        else:
            logger.info("Ignoring message, no '!' prefix or '=' found.")
        return ConversationHandler.END

    full_text = full_text[1:].strip()
    full_text_fixed = full_text.replace(
        '“', '"').replace('”', '"').replace("‘", "'").replace("’", "'")

    try:
        parts = shlex.split(full_text_fixed)
    except ValueError as e:
        logger.warning(f"Shlex parsing error: {e}. Likely an unclosed quote.")
        await update.message.reply_text(
            t("command.parse_error", context, error=e)
        )
        return ConversationHandler.END

    if not parts:
        return ConversationHandler.END

    command = parts[0].lower()
    args = parts[1:]
    user_id = context.user_data['user_profile']['_id']

    try:
        if full_text.lower().startswith("repaid by") or \
                full_text.lower().startswith("paid by"):
            args = parts[2:]
            await handle_repayment(update, context, args, debt_type='lent')
            return ConversationHandler.END

        if command in ["paid", "repaid"]:
            await handle_repayment(update, context, args, debt_type='borrowed')
            return ConversationHandler.END

        tx_data, debt_data, base_text = None, None, None

        if command in ["expense", "income"]:
            tx_data, base_text = await handle_generic_transaction(
                update, context, command, args
            )
        elif command in ["lent", "borrowed"]:
            debt_data, base_text = await handle_generic_debt(
                update, context, command, args
            )
        elif command in COMMAND_MAP:
            tx_data, base_text = await handle_quick_command(
                update, context, command, args
            )
        else:
            context.user_data['unknown_command_data'] = {
                'command': command, 'args': args
            }
            return await unknown_command_entry_point(update, context)

        if tx_data:
            response = api_client.add_transaction(tx_data, user_id)
            if not response:
                base_text = t("command.tx_fail", context)
        elif debt_data:
            response = api_client.add_debt(debt_data, user_id)
            if not response:
                base_text = t("command.debt_fail", context)

        if (tx_data or debt_data) and base_text:
            summary_text = format_summary_message(
                api_client.get_detailed_summary(user_id), context
            )
            await update.message.reply_text(
                base_text + summary_text,
                parse_mode='HTML',
                reply_markup=keyboards.main_menu_keyboard(context)
            )

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in unified_message_router: {e}", exc_info=True)
        await update.message.reply_text(t("command.error_parsing", context))
        return ConversationHandler.END


# --- UNKNOWN ITEM CONVERSATION ---
async def unknown_command_entry_point(update: Update,
                                      context: ContextTypes.DEFAULT_TYPE):
    """Entry point for handling unknown commands as potential expenses."""
    try:
        data = context.user_data['unknown_command_data']
        command, args = data['command'], data['args']
        tx_date, args_without_date = parse_date_from_args(args)

        if not args_without_date:
            await update.message.reply_text(
                t("command.unknown_fail", context)
            )
            return ConversationHandler.END

        amount_str = args_without_date[-1]
        description_parts = args_without_date[:-1]

        try:
            amount, currency = parse_amount_and_currency(amount_str)
        except ValueError:
            await update.message.reply_text(t("command.unknown_fail", context))
            return ConversationHandler.END

        description = command.replace('_', ' ').title()
        if description_parts:
            description += f" {' '.join(description_parts)}"

        context.user_data['new_tx'] = {
            "type": "expense", "amount": amount, "currency": currency,
            "accountName": f"{currency} Account", "description": description,
            "timestamp": tx_date
        }

        amount_display = (f"{amount:,.0f} {currency}" if currency == 'KHR'
                          else f"${amount:,.2f}")

        # Get user's dynamic categories
        profile = context.user_data['user_profile']
        all_categories = profile.get('settings', {}).get('categories', {})
        user_categories = all_categories.get('expense', [])
        keyboard = keyboards.expense_categories_keyboard(user_categories,
                                                         context)

        await update.message.reply_text(
            t("command.unknown_prompt", context,
              description=description, amount_display=amount_display),
            reply_markup=keyboard
        )
        return SELECT_CATEGORY
    except Exception as e:
        logger.error(f"Error starting unknown command flow: {e}", exc_info=True)
        return ConversationHandler.END


async def received_category_for_unknown(update: Update,
                                        context: ContextTypes.DEFAULT_TYPE):
    """Handles category selection for the unknown command."""
    query = update.callback_query
    await query.answer()
    category = query.data.split('_')[1]

    if category == 'other':
        await query.edit_message_text(
            t("command.unknown_ask_custom", context)
        )
        return GET_CUSTOM_CATEGORY

    tx_data = context.user_data.get('new_tx')
    if not tx_data:
        return ConversationHandler.END

    tx_data['categoryId'] = category
    return await save_and_end_unknown(query.message, context)


async def received_text_for_custom_category(update: Update,
                                            context: ContextTypes.DEFAULT_TYPE):
    """Handles custom category text for the unknown command."""
    tx_data = context.user_data.get('new_tx')
    if not tx_data:
        return ConversationHandler.END

    tx_data['categoryId'] = update.message.text.strip().title()
    return await save_and_end_unknown(update.message, context)


async def save_and_end_unknown(message, context: ContextTypes.DEFAULT_TYPE):
    """Saves the transaction from the unknown command flow."""
    user_id = context.user_data['user_profile']['_id']
    tx_data = context.user_data.get('new_tx')
    if not tx_data:
        return ConversationHandler.END

    response = api_client.add_transaction(tx_data, user_id)

    base_text = (_format_success_message(tx_data)
                 if response else t("command.tx_fail", context))
    summary_text = format_summary_message(
        api_client.get_detailed_summary(user_id), context
    )

    await message.reply_text(
        base_text + summary_text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard(context)
    )
    return ConversationHandler.END


unified_message_conversation_handler = ConversationHandler(
    entry_points=[MessageHandler(
        filters.TEXT & ~filters.COMMAND, unified_message_router
    )],
    states={
        SELECT_CATEGORY: [CallbackQueryHandler(
            received_category_for_unknown, pattern='^cat_'
        )],
        GET_CUSTOM_CATEGORY: [MessageHandler(
            filters.TEXT & ~filters.COMMAND, received_text_for_custom_category
        )],
    },
    fallbacks=[
        CommandHandler('cancel', cancel),
        CommandHandler('start', start),
        CallbackQueryHandler(start, pattern='^start$')
    ],
    per_message=False,
    conversation_timeout=60
)
# --- End of modified file ---