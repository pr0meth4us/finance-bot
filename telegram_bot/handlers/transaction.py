import re
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import api_client
import keyboards
from .common import start
from decorators import authenticate_user
from utils.i18n import t

(
    AMOUNT, CURRENCY, CATEGORY, CUSTOM_CATEGORY, ASK_REMARK, REMARK,
    FORGOT_DATE, FORGOT_CUSTOM_DATE, FORGOT_TYPE,
    EDIT_CHOOSE_FIELD, EDIT_GET_NEW_VALUE, EDIT_GET_NEW_CATEGORY,
    EDIT_GET_CUSTOM_CATEGORY, EDIT_GET_NEW_DATE, EDIT_GET_NEW_CURRENCY
) = range(15)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")


def _get_tx_settings(context):
    profile = context.user_data.get('profile', {})
    settings = profile.get('settings', {})
    mode = settings.get('currency_mode', 'dual')
    primary = settings.get('primary_currency', 'USD') if mode == 'single' else 'USD'
    return mode, primary


def parse_amount_and_currency_for_mode(amount_str: str, mode: str, primary_currency: str):
    """Returns (amount, currency, is_ambiguous)."""
    s = amount_str.lower().strip()
    if mode == 'single':
        try:
            return float(re.sub(r"[^0-9.]", "", s)), primary_currency, False
        except ValueError:
            raise ValueError("Invalid amount")

    if 'khr' in s:
        return float(s.replace('khr', '').strip()), 'KHR', False

    try:
        # Check if explicitly USD (regex would be better but simple check is okay for now)
        return float(re.sub(r"[^0-9.]", "", s)), 'USD', True  # Ambiguous
    except ValueError:
        raise ValueError("Invalid amount")


# --- Add Transaction ---

@authenticate_user
async def add_transaction_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Reset tx state
    for k in ['tx_amount', 'tx_currency', 'tx_category', 'tx_remark', 'timestamp']:
        context.user_data.pop(k, None)

    tx_type = 'expense' if query.data == 'add_expense' else 'income'
    context.user_data['tx_type'] = tx_type
    emoji = "💸" if tx_type == 'expense' else "💰"

    await query.message.reply_text(t("tx.ask_amount", context, emoji=emoji))
    return AMOUNT


@authenticate_user
async def received_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mode, primary = _get_tx_settings(context)
        amt, curr, ambiguous = parse_amount_and_currency_for_mode(update.message.text, mode, primary)
        context.user_data['tx_amount'] = amt

        if mode == 'single' or not ambiguous:
            context.user_data['tx_currency'] = curr
            await _ask_category(update.message, context, amt, curr)
            return CATEGORY

        await update.message.reply_text(t("tx.ask_currency", context),
                                        reply_markup=keyboards.currency_keyboard(context))
        return CURRENCY
    except ValueError:
        await update.message.reply_text(t("tx.invalid_amount", context))
        return AMOUNT


@authenticate_user
async def received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    curr = query.data.split('_')[1]
    context.user_data['tx_currency'] = curr
    await _ask_category(query.message, context, 0, curr, show_amount=False)
    return CATEGORY


async def _ask_category(message, context, amt, curr, show_amount=True):
    cats = context.user_data['profile'].get('settings', {}).get('categories', {}).get(context.user_data['tx_type'], [])
    kb_func = keyboards.expense_categories_keyboard if context.user_data[
                                                           'tx_type'] == 'expense' else keyboards.income_categories_keyboard
    kb = kb_func(cats, context)

    if show_amount:
        fmt = ",.0f" if curr == 'KHR' else ",.2f"
        text = t("tx.ask_category", context, amount_display=f"{amt:{fmt}} {curr}")
    else:
        text = t("tx.ask_category_curr", context, currency=curr)

    if message.from_user.is_bot:
        await message.edit_text(text, parse_mode='HTML', reply_markup=kb)
    else:
        await message.reply_text(text, parse_mode='HTML', reply_markup=kb)


@authenticate_user
async def received_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = query.data.split('_')[1]

    if cat == 'other':
        await query.edit_message_text(t("tx.ask_custom_category", context))
        return CUSTOM_CATEGORY

    context.user_data['tx_category'] = cat
    await _ask_remark(query.message, context, cat)
    return ASK_REMARK


@authenticate_user
async def received_custom_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat = update.message.text.strip().title()
    context.user_data['tx_category'] = cat
    await _ask_remark(update.message, context, cat)
    return ASK_REMARK


async def _ask_remark(message, context, category):
    text = t("tx.ask_remark", context, category=category)
    kb = keyboards.ask_remark_keyboard(context)

    if message.from_user.is_bot:
        await message.edit_text(text, parse_mode='HTML', reply_markup=kb)
    else:
        await message.reply_text(text, parse_mode='HTML', reply_markup=kb)


@authenticate_user
async def ask_remark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if 'yes' in query.data:
        await query.edit_message_text(t("tx.ask_remark_prompt", context))
        return REMARK

    context.user_data['tx_remark'] = ""
    return await save_transaction_and_end(update, context)


@authenticate_user
async def received_remark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['tx_remark'] = update.message.text
    return await save_transaction_and_end(update, context)


async def save_transaction_and_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data
    payload = {
        "type": d['tx_type'], "amount": d['tx_amount'], "currency": d['tx_currency'],
        "categoryId": d['tx_category'], "accountName": f"{d['tx_currency']} Account",
        "description": d.get('tx_remark', ''), "timestamp": d.get('timestamp')
    }

    res = api_client.add_transaction(payload, d['jwt'])
    msg = t("tx.success", context) if 'id' in res else t("tx.fail", context)

    target = update.callback_query.message if update.callback_query else update.message
    await target.reply_text(msg, reply_markup=keyboards.main_menu_keyboard(context))
    return ConversationHandler.END


# --- Forgot Log ---

@authenticate_user
async def forgot_log_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(t("forgot.ask_day", context), reply_markup=keyboards.forgot_day_keyboard(context))
    return FORGOT_DATE


@authenticate_user
async def received_forgot_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split('_')[-1]

    if choice == 'custom':
        await query.message.reply_text(t("forgot.ask_date", context))
        return FORGOT_CUSTOM_DATE

    dt = datetime.now(PHNOM_PENH_TZ) - timedelta(days=int(choice))
    context.user_data['timestamp'] = dt.replace(hour=12, minute=0).isoformat()

    await query.message.reply_text(t("forgot.ask_type", context), reply_markup=keyboards.forgot_type_keyboard(context))
    return FORGOT_TYPE


@authenticate_user
async def received_forgot_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        d = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['timestamp'] = datetime.combine(d, time(12, 0), tzinfo=PHNOM_PENH_TZ).isoformat()
        await update.message.reply_text(t("forgot.ask_type", context),
                                        reply_markup=keyboards.forgot_type_keyboard(context))
        return FORGOT_TYPE
    except ValueError:
        await update.message.reply_text(t("forgot.invalid_date", context))
        return FORGOT_CUSTOM_DATE


@authenticate_user
async def received_forgot_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['tx_type'] = query.data.split('_')[-1]
    await query.message.reply_text(t("tx.ask_amount", context, emoji=""), parse_mode='HTML')
    return AMOUNT


# --- History & Management ---

@authenticate_user
async def history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    txs = api_client.get_recent_transactions(context.user_data['jwt'])

    if not txs:
        await query.edit_message_text(t("history.no_tx", context), reply_markup=keyboards.main_menu_keyboard(context))
        return ConversationHandler.END

    await query.edit_message_text(t("history.menu_header", context),
                                  reply_markup=keyboards.history_keyboard(txs, context))
    return ConversationHandler.END


@authenticate_user
async def manage_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tx_id = query.data.replace('manage_tx_', '')
    tx = api_client.get_transaction_details(tx_id, context.user_data['jwt'])

    if not tx:
        await query.edit_message_text(t("history.fetch_fail", context),
                                      reply_markup=keyboards.main_menu_keyboard(context))
        return

    emoji = "⬇️ Expense" if tx['type'] == 'expense' else "⬆️ Income"
    date_str = datetime.fromisoformat(tx['timestamp']).astimezone(PHNOM_PENH_TZ).strftime('%d %b %Y, %I:%M %p')
    fmt = ",.0f" if tx['currency'] == 'KHR' else ",.2f"

    text = t("history.tx_details", context, emoji=emoji, amount=f"{tx['amount']:{fmt}}", currency=tx['currency'],
             category=tx['categoryId'], description=tx.get('description', 'N/A'), date=date_str)

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboards.manage_tx_keyboard(tx_id, context))


@authenticate_user
async def delete_transaction_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tx_id = query.data.replace('delete_tx_', '')
    await query.edit_message_text(t("history.delete_prompt", context), parse_mode='HTML',
                                  reply_markup=keyboards.confirm_delete_keyboard(tx_id, context))


@authenticate_user
async def delete_transaction_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tx_id = query.data.replace('confirm_delete_', '')

    res = api_client.delete_transaction(tx_id, context.user_data['jwt'])
    msg = t("history.delete_success", context) if res else t("history.delete_fail", context)

    await query.edit_message_text(msg, reply_markup=keyboards.main_menu_keyboard(context))
    return ConversationHandler.END


# --- Edit Transaction ---

@authenticate_user
async def edit_transaction_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tx_id = query.data.replace('edit_tx_', '')

    tx = api_client.get_transaction_details(tx_id, context.user_data['jwt'])
    if not tx:
        await query.edit_message_text(t("history.edit_fail", context))
        return ConversationHandler.END

    context.user_data.update({'edit_tx_id': tx_id, 'edit_tx_type': tx['type']})
    await query.edit_message_text(t("history.edit_ask_field", context),
                                  reply_markup=keyboards.edit_tx_options_keyboard(tx_id, context))
    return EDIT_CHOOSE_FIELD


@authenticate_user
async def edit_choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.split('_')[2]
    context.user_data['edit_field'] = field

    if field == 'categoryId':
        cats = context.user_data['profile']['settings']['categories'][context.user_data['edit_tx_type']]
        kb = keyboards.expense_categories_keyboard(cats, context) if context.user_data[
                                                                         'edit_tx_type'] == 'expense' else keyboards.income_categories_keyboard(
            cats, context)
        await query.edit_message_text(t("history.edit_ask_new_category", context), reply_markup=kb)
        return EDIT_GET_NEW_CATEGORY

    if field == 'currency':
        await query.edit_message_text(t("history.edit_ask_new_currency", context),
                                      reply_markup=keyboards.currency_keyboard(context))
        return EDIT_GET_NEW_CURRENCY

    key_map = {'amount': 'new_amount', 'description': 'new_desc', 'timestamp': 'new_date'}
    await query.edit_message_text(t(f"history.edit_ask_{key_map[field]}", context))
    return EDIT_GET_NEW_DATE if field == 'timestamp' else EDIT_GET_NEW_VALUE


@authenticate_user
async def edit_received_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text
    if context.user_data['edit_field'] == 'amount':
        try:
            float(val)
        except ValueError:
            await update.message.reply_text(t("history.edit_invalid_amount", context))
            return EDIT_GET_NEW_VALUE

    return await _save_edit(update, context, val)


@authenticate_user
async def edit_received_new_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        d = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        dt = datetime.combine(d, time(12, 0), tzinfo=PHNOM_PENH_TZ).isoformat()
        return await _save_edit(update, context, dt)
    except ValueError:
        await update.message.reply_text(t("history.edit_invalid_date", context))
        return EDIT_GET_NEW_DATE


@authenticate_user
async def edit_received_new_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = query.data.split('_')[1]
    if cat == 'other':
        await query.edit_message_text(t("tx.ask_custom_category", context))
        return EDIT_GET_CUSTOM_CATEGORY
    return await _save_edit(query, context, cat)


@authenticate_user
async def edit_received_custom_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _save_edit(update, context, update.message.text.strip().title())


async def _save_edit(update_obj, context, val):
    d = context.user_data
    payload = {d['edit_field']: val}
    if d['edit_field'] == 'currency':
        payload['accountName'] = f"{val} Account"

    res = api_client.update_transaction(d['edit_tx_id'], payload, d['jwt'])

    msg = t("history.edit_success", context) if res.get('message') else t("history.edit_update_fail", context,
                                                                          error=res.get('error'))

    target = update_obj.message if isinstance(update_obj, Update) else update_obj
    await target.reply_text(msg, reply_markup=keyboards.main_menu_keyboard(context))
    return ConversationHandler.END