# telegram_bot/handlers/command_handler.py

import re
import shlex
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from asteval import Interpreter
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters, CommandHandler
)

import api_client
import keyboards
from decorators import authenticate_user
from .helpers import format_summary_message
# FIXED: Import 'menu' instead of 'start'
from .common import cancel, menu
from utils.i18n import t

log = logging.getLogger(__name__)
PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")
aeval = Interpreter()

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
    'investment': {'categoryId': 'Investment', 'description': 'Investment', 'type': 'expense'},
    'salary': {'categoryId': 'Salary', 'description': 'Salary', 'type': 'income'},
    'bonus': {'categoryId': 'Bonus', 'description': 'Bonus', 'type': 'income'},
    'commission': {'categoryId': 'Commission', 'description': 'Commission', 'type': 'income'},
    'allowance': {'categoryId': 'Allowance', 'description': 'Allowance', 'type': 'income'},
    'gift': {'categoryId': 'Gift', 'description': 'Gift', 'type': 'income'},
}


def _get_currency_settings(context):
    profile = context.user_data.get('profile', {})
    settings = profile.get('settings', {})
    mode = settings.get('currency_mode', 'dual')
    primary = settings.get('primary_currency', 'USD') if mode == 'single' else 'USD'
    return mode, primary


def parse_amount_and_currency(amount_str: str, mode: str, primary_currency: str):
    amount_str = amount_str.lower().strip()

    if mode == 'single':
        try:
            val = float(re.sub(r"[^0-9.]", "", amount_str))
            return val, primary_currency
        except ValueError:
            raise ValueError("Invalid amount")

    # Dual Mode
    if 'khr' in amount_str:
        return float(amount_str.replace('khr', '').strip()), 'KHR'

    # Default to USD if ambiguous but parsable
    return float(amount_str), 'USD'


def parse_date(args):
    if not args: return None, args

    date_str = args[-1]
    today = datetime.now(PHNOM_PENH_TZ)

    for fmt in ('%m-%d', '%d-%m'):
        try:
            parsed = datetime.strptime(date_str, fmt)
            dt = today.replace(month=parsed.month, day=parsed.day, hour=12, minute=0)
            return dt.isoformat(), args[:-1]
        except ValueError:
            continue

    return None, args


def _format_success(data, context):
    lines = [t("command.success_header", context)]

    type_key = "common.expense_word" if data.get('type') == 'expense' else "common.income_word"
    lines.append(t("command.success_type", context, type=t(type_key, context)))

    amt = data.get('amount') or data.get('iou_amount')
    curr = data.get('currency') or data.get('iou_currency')
    fmt = ",.0f" if curr == 'KHR' else ",.2f"
    lines.append(t("command.success_amount", context, amount_display=f"{amt:{fmt}} {curr}"))

    if 'categoryId' in data:
        cat = t(f"categories.{data['categoryId']}", context)
        lines.append(t("command.success_category", context, category=cat))
        if data.get('description'):
            lines.append(t("command.success_description", context, description=data['description']))

    elif 'person' in data:
        lines.append(t("command.success_person", context, person=data['person']))
        if data.get('purpose'):
            lines.append(t("command.success_purpose", context, purpose=data['purpose']))

    date_str = datetime.fromisoformat(data['timestamp']).strftime('%Y-%m-%d') if data.get(
        'timestamp') else datetime.now().strftime('%Y-%m-%d')
    lines.append(t("command.success_date", context, date=date_str))

    return "\n".join(lines)


@authenticate_user
async def handle_transaction_command(update, context, command, args):
    try:
        if len(args) < 2:
            await update.message.reply_text(t("command.invalid_format_generic", context, command=command),
                                            parse_mode='Markdown')
            return None

        mode, primary = _get_currency_settings(context)
        date_str, remaining = parse_date(args)

        amount_val, currency = parse_amount_and_currency(remaining[-1], mode, primary)
        category = remaining[0].strip().title()
        description = " ".join(remaining[1:-1])

        tx_data = {
            "type": command, "amount": amount_val, "currency": currency,
            "accountName": f"{currency} Account", "categoryId": category,
            "description": description, "timestamp": date_str
        }
        return tx_data, _format_success(tx_data, context)
    except Exception as e:
        log.error(f"Command error: {e}")
        await update.message.reply_text(t("command.error_parsing", context))
        return None


@authenticate_user
async def handle_debt_command(update, context, command, args):
    try:
        if len(args) < 2:
            await update.message.reply_text(t("command.invalid_format_debt", context, command=command),
                                            parse_mode='Markdown')
            return None

        mode, primary = _get_currency_settings(context)
        date_str, remaining = parse_date(args)

        person = remaining[0]
        amount_val, currency = parse_amount_and_currency(remaining[1], mode, primary)
        purpose = " ".join(remaining[2:])

        debt_data = {
            "type": command, "person": person, "amount": amount_val,
            "currency": currency, "purpose": purpose, "timestamp": date_str
        }
        return debt_data, _format_success(debt_data, context)
    except Exception as e:
        log.error(f"Debt command error: {e}")
        await update.message.reply_text(t("command.error_parsing", context))
        return None


@authenticate_user
async def handle_quick_command(update, context, command, args):
    try:
        mode, primary = _get_currency_settings(context)
        date_str, remaining = parse_date(args)

        if not remaining:
            await update.message.reply_text(t("command.invalid_format_missing_amount", context))
            return None

        amount_val, currency = parse_amount_and_currency(remaining[-1], mode, primary)
        desc_parts = remaining[:-1]
        details = COMMAND_MAP[command]

        desc = " ".join(desc_parts) if desc_parts else details['description']

        tx_data = {
            "type": details['type'], "amount": amount_val, "currency": currency,
            "accountName": f"{currency} Account", "categoryId": details['categoryId'],
            "description": desc, "timestamp": date_str
        }
        return tx_data, _format_success(tx_data, context)
    except Exception as e:
        log.error(f"Quick command error: {e}")
        await update.message.reply_text(t("command.error_generic", context))
        return None


@authenticate_user
async def handle_repayment(update, context, args, debt_type):
    try:
        mode, primary = _get_currency_settings(context)
        date_str, remaining = parse_date(args)

        if len(remaining) < 2:
            ex = "`!repaid by <Person> <Amount>`" if debt_type == 'lent' else "`!paid <Person> <Amount>`"
            await update.message.reply_text(t("command.invalid_format_repayment", context, example=ex),
                                            parse_mode='Markdown')
            return

        person = remaining[0]
        amount, currency = parse_amount_and_currency(remaining[1], mode, primary)

        response = api_client.record_lump_sum_repayment(
            person, currency, amount, debt_type, context.user_data['jwt'], date_str
        )

        text = response.get('message') or t("command.repayment_error", context, error=response.get('error'))

        summary = api_client.get_detailed_summary(context.user_data['jwt'])
        await update.message.reply_text(text + format_summary_message(summary, context), parse_mode='HTML')

    except Exception as e:
        log.error(f"Repayment error: {e}")
        await update.message.reply_text(t("command.repayment_fail", context))


async def unified_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # Calculator
    if not text.startswith('!') and '=' in text:
        expression = text.split('=')[0].strip()
        try:
            result = aeval.eval(expression)
            await update.message.reply_text(t("command.calculating", context, result=result), parse_mode='Markdown')
        except Exception:
            await update.message.reply_text(t("command.calculator_fail", context))
        return ConversationHandler.END

    if not text.startswith('!'):
        return ConversationHandler.END

    # Command Parsing
    try:
        parts = shlex.split(text[1:].replace('“', '"').replace('”', '"').replace("‘", "'").replace("’", "'"))
    except ValueError as e:
        await update.message.reply_text(t("command.parse_error", context, error=str(e)))
        return ConversationHandler.END

    if not parts: return ConversationHandler.END

    command = parts[0].lower()
    args = parts[1:]

    # Check Profile for Auth
    if not context.user_data.get('profile'):
        log.info("Auth check delegated to decorated handlers.")

    # Route
    if text.lower().startswith("!repaid by") or text.lower().startswith("!paid by"):
        await handle_repayment(update, context, parts[2:], 'lent')
        return ConversationHandler.END

    if command in ["paid", "repaid"]:
        await handle_repayment(update, context, args, 'borrowed')
        return ConversationHandler.END

    result = None

    if command in ["expense", "income"]:
        result = await handle_transaction_command(update, context, command, args)
        if result:
            api_client.add_transaction(result[0], context.user_data['jwt'])

    elif command in ["lent", "borrowed"]:
        result = await handle_debt_command(update, context, command, args)
        if result:
            api_client.add_debt(result[0], context.user_data['jwt'])

    elif command in COMMAND_MAP:
        result = await handle_quick_command(update, context, command, args)
        if result:
            api_client.add_transaction(result[0], context.user_data['jwt'])

    else:
        context.user_data['unknown_cmd'] = {'command': command, 'args': args}
        return await unknown_command_entry_point(update, context)

    if result:
        summary = api_client.get_detailed_summary(context.user_data['jwt'])
        await update.message.reply_text(result[1] + format_summary_message(summary, context), parse_mode='HTML',
                                        reply_markup=keyboards.main_menu_keyboard(context))

    return ConversationHandler.END


# --- Unknown Command Flow ---

@authenticate_user
async def unknown_command_entry_point(update, context):
    try:
        data = context.user_data['unknown_cmd']
        cmd, args = data['command'], data['args']
        date_str, remaining = parse_date(args)

        if not remaining:
            await update.message.reply_text(t("command.unknown_fail", context))
            return ConversationHandler.END

        mode, primary = _get_currency_settings(context)
        amount_val, currency = parse_amount_and_currency(remaining[-1], mode, primary)
        desc_parts = remaining[:-1]

        desc = cmd.replace('_', ' ').title() + (" " + " ".join(desc_parts) if desc_parts else "")

        context.user_data['new_tx'] = {
            "type": "expense", "amount": amount_val, "currency": currency,
            "accountName": f"{currency} Account", "description": desc, "timestamp": date_str
        }

        fmt = ",.0f" if currency == 'KHR' else ",.2f"
        display = f"{amount_val:{fmt}} {currency}"

        cats = context.user_data['profile'].get('settings', {}).get('categories', {}).get('expense', [])
        kb = keyboards.expense_categories_keyboard(cats, context)

        await update.message.reply_text(t("command.unknown_prompt", context, description=desc, amount_display=display),
                                        reply_markup=kb)
        return SELECT_CATEGORY
    except Exception as e:
        log.error(f"Unknown cmd error: {e}")
        return ConversationHandler.END


async def received_category_for_unknown(update, context):
    query = update.callback_query
    await query.answer()
    cat = query.data.split('_')[1]

    if cat == 'other':
        await query.edit_message_text(t("command.unknown_ask_custom", context))
        return GET_CUSTOM_CATEGORY

    context.user_data['new_tx']['categoryId'] = cat
    return await save_unknown_tx(query.message, context)


async def received_custom_category_unknown(update, context):
    context.user_data['new_tx']['categoryId'] = update.message.text.strip().title()
    return await save_unknown_tx(update.message, context)


async def save_unknown_tx(message, context):
    tx = context.user_data.pop('new_tx')
    api_client.add_transaction(tx, context.user_data['jwt'])

    summary = api_client.get_detailed_summary(context.user_data['jwt'])
    msg = _format_success(tx, context) + format_summary_message(summary, context)

    await message.reply_text(msg, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard(context))
    return ConversationHandler.END


unified_message_conversation_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, unified_message_router)],
    states={
        SELECT_CATEGORY: [CallbackQueryHandler(received_category_for_unknown, pattern='^cat_')],
        GET_CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_custom_category_unknown)],
    },
    fallbacks=[
        CommandHandler('cancel', cancel),
        # FIXED: Support menu command
        CommandHandler('menu', menu)
    ],
    per_message=False
)