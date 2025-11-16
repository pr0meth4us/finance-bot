# --- Start of file: telegram_bot/handlers/transaction.py ---

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import re
import api_client
import keyboards
from .common import start, cancel
from decorators import authenticate_user
from utils.i18n import t

# Conversation states
(
    AMOUNT, CURRENCY, CATEGORY, CUSTOM_CATEGORY, ASK_REMARK, REMARK,
    FORGOT_DATE, FORGOT_CUSTOM_DATE, FORGOT_TYPE,
    EDIT_CHOOSE_FIELD, EDIT_GET_NEW_VALUE, EDIT_GET_NEW_CATEGORY,
    EDIT_GET_CUSTOM_CATEGORY, EDIT_GET_NEW_DATE, EDIT_GET_NEW_CURRENCY
) = range(15)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")


def _get_user_settings_for_tx(context: ContextTypes.DEFAULT_TYPE):
    """Helper to get currency mode and primary currency."""
    profile = context.user_data.get('profile', {})

    settings = profile.get('settings', {})
    mode = settings.get('currency_mode', 'dual')

    if mode == 'single':
        primary_currency = settings.get('primary_currency', 'USD')
        return mode, (primary_currency,)

    return 'dual', ('USD', 'KHR')


def parse_amount_and_currency_for_mode(amount_str: str, mode: str, primary_currency: str):
    """
    Parses an amount string based on the user's currency mode.
    Returns (amount, currency, is_ambiguous)
    """
    amount_str = amount_str.lower().strip()

    if mode == 'single':
        try:
            # In single mode, just strip all non-numeric characters
            amount_val = float(re.sub(r"[^0-9.]", "", amount_str))
            return amount_val, primary_currency, False
        except ValueError:
            raise ValueError("Invalid amount for single currency mode")

    # Dual-currency mode logic
    try:
        if 'khr' in amount_str:
            amount_val = float(amount_str.replace('khr', '').strip())
            return amount_val, 'KHR', False

        # Check if it's just a number (ambiguous)
        amount_val = float(amount_str)
        return amount_val, None, True  # Ambiguous, default to USD but ask

    except ValueError:
        # Check if it has 'usd' or '$'
        amount_val_str = re.sub(r"[^0-9.]", "", amount_str)
        if amount_val_str:
            amount_val = float(amount_val_str)
            return amount_val, 'USD', False

        raise ValueError("Invalid amount for dual currency mode")


# --- Add Transaction Flow ---

@authenticate_user
async def add_transaction_start(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    """Starts the add transaction flow by asking for the amount."""
    query = update.callback_query
    await query.answer()

    # --- REFACTOR: Preserve auth cache ---
    jwt = context.user_data.get('jwt')
    profile_data = context.user_data.get('profile_data')
    profile = context.user_data.get('profile')
    role = context.user_data.get('role')
    context.user_data.clear()
    context.user_data['jwt'] = jwt
    context.user_data['profile_data'] = profile_data
    context.user_data['profile'] = profile
    context.user_data['role'] = role
    # ---

    tx_type = 'expense' if query.data == 'add_expense' else 'income'
    context.user_data['tx_type'] = tx_type
    emoji = "💸" if tx_type == 'expense' else "💰"

    await query.message.reply_text(t("tx.ask_amount", context, emoji=emoji))
    return AMOUNT


@authenticate_user
async def received_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives amount, parses it, and asks for category or currency."""
    try:
        mode, currencies = _get_user_settings_for_tx(context)
        primary_currency = currencies[0] if mode == 'single' else 'USD'

        amount_str = update.message.text
        amount, currency, is_ambiguous = parse_amount_and_currency_for_mode(
            amount_str, mode, primary_currency
        )

        context.user_data['tx_amount'] = amount

        # --- MODE-BASED LOGIC ---
        if mode == 'single' or not is_ambiguous:
            # Single mode OR Dual mode with explicit currency (e.g., "10khr")
            context.user_data['tx_currency'] = currency

            if currency == 'KHR':
                amount_display = f"{amount:,.0f} {currency}"
            else:
                amount_display = f"{amount:,.2f} {currency}"

            # Get user's dynamic categories
            profile = context.user_data['profile']
            tx_type = context.user_data['tx_type']
            all_categories = profile.get('settings', {}).get('categories', {})
            user_categories = all_categories.get(tx_type, [])

            if tx_type == 'expense':
                keyboard = keyboards.expense_categories_keyboard(user_categories,
                                                                 context)
            else:
                keyboard = keyboards.income_categories_keyboard(user_categories,
                                                                context)

            await update.message.reply_text(
                t("tx.ask_category", context, amount_display=amount_display),
                parse_mode='HTML',
                reply_markup=keyboard
            )
            return CATEGORY

        else:
            # Dual mode and ambiguous (e.g., "10")
            # Ask for currency
            await update.message.reply_text(
                t("tx.ask_currency", context),
                reply_markup=keyboards.currency_keyboard(context)
            )
            return CURRENCY

    except ValueError:
        await update.message.reply_text(t("tx.invalid_amount", context))
        return AMOUNT


@authenticate_user
async def received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives currency (if amount was ambiguous) and asks for category."""
    query = update.callback_query
    await query.answer()
    currency = query.data.split('_')[1]
    context.user_data['tx_currency'] = currency

    # Get user's dynamic categories
    profile = context.user_data['profile']
    tx_type = context.user_data['tx_type']
    all_categories = profile.get('settings', {}).get('categories', {})
    user_categories = all_categories.get(tx_type, [])

    if tx_type == 'expense':
        keyboard = keyboards.expense_categories_keyboard(user_categories,
                                                         context)
    else:
        keyboard = keyboards.income_categories_keyboard(user_categories,
                                                        context)

    await query.edit_message_text(
        t("tx.ask_category_curr", context, currency=currency),
        parse_mode='HTML',
        reply_markup=keyboard
    )
    return CATEGORY


@authenticate_user
async def received_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives category and asks for a remark."""
    query = update.callback_query
    await query.answer()
    category = query.data.split('_')[1]

    if category == 'other':
        await query.edit_message_text(
            t("tx.ask_custom_category", context)
        )
        return CUSTOM_CATEGORY

    context.user_data['tx_category'] = category
    await query.edit_message_text(
        t("tx.ask_remark", context, category=category),
        parse_mode='HTML',
        reply_markup=keyboards.ask_remark_keyboard(context)
    )
    return ASK_REMARK


@authenticate_user
async def received_custom_category(update: Update,
                                   context: ContextTypes.DEFAULT_TYPE):
    """Receives custom category name and asks for a remark."""
    category = update.message.text.strip().title()
    context.user_data['tx_category'] = category
    await update.message.reply_text(
        t("tx.ask_remark", context, category=category),
        parse_mode='HTML',
        reply_markup=keyboards.ask_remark_keyboard(context)
    )
    return ASK_REMARK


@authenticate_user
async def ask_remark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles 'Add Remark' or 'Skip' button press."""
    query = update.callback_query
    await query.answer()
    choice = query.data.split('_')[1]

    if choice == 'yes':
        await query.edit_message_text(t("tx.ask_remark_prompt", context))
        return REMARK
    if choice == 'no':
        context.user_data['tx_remark'] = ""
        return await save_transaction_and_end(update, context)
    return ConversationHandler.END


@authenticate_user
async def received_remark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the remark text and saves the transaction."""
    context.user_data['tx_remark'] = update.message.text
    return await save_transaction_and_end(update, context)


async def save_transaction_and_end(update: Update,
                                   context: ContextTypes.DEFAULT_TYPE):
    """Final step: construct and save the transaction to the API."""
    try:
        jwt = context.user_data['jwt']
        data = context.user_data
        tx_data = {
            "type": data['tx_type'],
            "amount": data['tx_amount'],
            "currency": data['tx_currency'],
            "categoryId": data['tx_category'],
            "accountName": f"{data['tx_currency']} Account",
            "description": data.get('tx_remark', ''),
            "timestamp": data.get('timestamp')  # None if not set
        }

        response = api_client.add_transaction(tx_data, jwt)
        message = (t("tx.success", context)
                   if response and "error" not in response
                   else t("tx.fail", context))

        if update.callback_query:
            await update.callback_query.message.reply_text(
                message, reply_markup=keyboards.main_menu_keyboard(context)
            )
        else:
            await update.message.reply_text(
                message, reply_markup=keyboards.main_menu_keyboard(context)
            )

        # --- THIS IS THE FIX ---
        # Clear only conversation state, not auth state
        context.user_data.pop('tx_type', None)
        context.user_data.pop('tx_amount', None)
        context.user_data.pop('tx_currency', None)
        context.user_data.pop('tx_category', None)
        context.user_data.pop('tx_remark', None)
        context.user_data.pop('timestamp', None)
        # --- END FIX ---

        return ConversationHandler.END
    except Exception as e:
        await (update.message or update.callback_query.message).reply_text(
            t("common.error_generic", context, error=e)
        )
        return await start(update, context)


# --- Forgot to Log Flow ---

@authenticate_user
async def forgot_log_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the 'forgot to log' flow by asking for the day."""
    query = update.callback_query
    await query.answer()

    # --- REFACTOR: Preserve auth cache ---
    jwt = context.user_data.get('jwt')
    profile_data = context.user_data.get('profile_data')
    profile = context.user_data.get('profile')
    role = context.user_data.get('role')
    context.user_data.clear()
    context.user_data['jwt'] = jwt
    context.user_data['profile_data'] = profile_data
    context.user_data['profile'] = profile
    context.user_data['role'] = role
    # ---

    await query.message.reply_text(
        t("forgot.ask_day", context),
        reply_markup=keyboards.forgot_day_keyboard(context)
    )
    return FORGOT_DATE


@authenticate_user
async def received_forgot_day(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    """Handles the day choice (Yesterday, Custom) for the forgot flow."""
    query = update.callback_query
    await query.answer()
    choice = query.data.split('_')[-1]

    if choice == 'custom':
        await query.message.reply_text(t("forgot.ask_date", context))
        return FORGOT_CUSTOM_DATE

    days_ago = int(choice)
    tx_date = datetime.now(PHNOM_PENH_TZ).date() - timedelta(days=days_ago)
    tx_datetime = datetime.combine(tx_date, time(12, 0), tzinfo=PHNOM_PENH_TZ)
    context.user_data['timestamp'] = tx_datetime.isoformat()

    await query.message.reply_text(
        t("forgot.ask_type", context),
        reply_markup=keyboards.forgot_type_keyboard(context)
    )
    return FORGOT_TYPE


@authenticate_user
async def received_forgot_custom_date(update: Update,
                                      context: ContextTypes.DEFAULT_TYPE):
    """Receives and validates the custom date for the forgot flow."""
    try:
        custom_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        tx_datetime = datetime.combine(
            custom_date, time(12, 0), tzinfo=PHNOM_PENH_TZ
        )
        context.user_data['timestamp'] = tx_datetime.isoformat()
        await update.message.reply_text(
            t("forgot.ask_type", context),
            reply_markup=keyboards.forgot_type_keyboard(context)
        )
        return FORGOT_TYPE
    except ValueError:
        await update.message.reply_text(t("forgot.invalid_date", context))
        return FORGOT_CUSTOM_DATE


@authenticate_user
async def received_forgot_type(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    """Receives the transaction type and asks for the amount."""
    query = update.callback_query
    await query.answer()
    tx_type = query.data.split('_')[-1]
    context.user_data['tx_type'] = tx_type
    await query.message.reply_text(
        t("forgot.ask_amount", context, type=tx_type.title()),
        parse_mode='HTML'
    )
    return AMOUNT  # Re-use the existing AMOUNT state


# --- History, Manage, Edit, Delete Flow ---

@authenticate_user
async def history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the last 20 transactions for the user."""
    query = update.callback_query
    await query.answer()

    jwt = context.user_data['jwt']
    transactions = api_client.get_recent_transactions(jwt)

    if not transactions:
        await query.edit_message_text(
            t("history.no_tx", context),
            reply_markup=keyboards.main_menu_keyboard(context)
        )
        return ConversationHandler.END

    await query.edit_message_text(
        t("history.menu_header", context),
        reply_markup=keyboards.history_keyboard(transactions, context)
    )
    return ConversationHandler.END


@authenticate_user
async def manage_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays details and edit/delete options for a single transaction."""
    query = update.callback_query
    await query.answer()

    jwt = context.user_data['jwt']
    tx_id = query.data.replace('manage_tx_', '')
    tx = api_client.get_transaction_details(tx_id, jwt)

    if not tx:
        await query.edit_message_text(
            t("history.fetch_fail", context),
            reply_markup=keyboards.history_keyboard([], context)
        )
        return

    emoji = "⬇️ Expense" if tx['type'] == 'expense' else "⬆️ Income"
    date_str = datetime.fromisoformat(
        tx['timestamp']
    ).astimezone(PHNOM_PENH_TZ).strftime('%d %b %Y, %I:%M %p')

    currency = tx.get('currency', 'USD')  # Default for safety
    amount_format = ",.0f" if currency == 'KHR' else ",.2f"
    amount = tx['amount']
    description = tx.get('description') or 'N/A'

    text = t("history.tx_details", context,
             emoji=emoji,
             amount=f"{amount:{amount_format}}",
             currency=currency,
             category=tx['categoryId'],
             description=description,
             date=date_str)

    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.manage_tx_keyboard(tx_id, context)
    )


@authenticate_user
async def delete_transaction_prompt(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE):
    """Asks the user to confirm deletion."""
    query = update.callback_query
    await query.answer()
    tx_id = query.data.replace('delete_tx_', '')
    await query.edit_message_text(
        t("history.delete_prompt", context),
        parse_mode='HTML',
        reply_markup=keyboards.confirm_delete_keyboard(tx_id, context)
    )


@authenticate_user
async def delete_transaction_confirm(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
    """Executes the deletion and shows the main menu."""
    query = update.callback_query
    await query.answer("Deleting...")

    jwt = context.user_data['jwt']
    tx_id = query.data.replace('confirm_delete_', '')
    success = api_client.delete_transaction(tx_id, jwt)

    message = (t("history.delete_success", context) if success
               else t("history.delete_fail", context))

    await query.edit_message_text(
        message,
        reply_markup=keyboards.main_menu_keyboard(context)
    )
    return ConversationHandler.END


# --- Edit Transaction Conversation ---

@authenticate_user
async def edit_transaction_start(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    """Asks which field to edit."""
    query = update.callback_query
    await query.answer()
    tx_id = query.data.replace('edit_tx_', '')

    # --- REFACTOR: Preserve auth cache ---
    jwt = context.user_data.get('jwt')
    profile_data = context.user_data.get('profile_data')
    profile = context.user_data.get('profile')
    role = context.user_data.get('role')
    context.user_data.clear()
    context.user_data['jwt'] = jwt
    context.user_data['profile_data'] = profile_data
    context.user_data['profile'] = profile
    context.user_data['role'] = role
    # ---

    context.user_data['edit_tx_id'] = tx_id

    tx = api_client.get_transaction_details(
        tx_id, context.user_data['jwt']  # Pass JWT
    )
    if not tx:
        await query.edit_message_text(t("history.edit_fail", context))
        return ConversationHandler.END

    context.user_data['edit_tx_type'] = tx['type']
    await query.edit_message_text(
        t("history.edit_ask_field", context),
        reply_markup=keyboards.edit_tx_options_keyboard(tx_id, context)
    )
    return EDIT_CHOOSE_FIELD


@authenticate_user
async def edit_choose_field(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    """Handles field choice and asks for the new value."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    field = parts[2]
    context.user_data['edit_field'] = field

    if field == 'categoryId':
        tx_type = context.user_data['edit_tx_type']
        profile = context.user_data['profile']
        all_categories = profile.get('settings', {}).get('categories', {})
        user_categories = all_categories.get(tx_type, [])

        if tx_type == 'expense':
            keyboard = keyboards.expense_categories_keyboard(user_categories,
                                                             context)
        else:
            keyboard = keyboards.income_categories_keyboard(user_categories,
                                                            context)
        await query.edit_message_text(
            t("history.edit_ask_new_category", context),
            reply_markup=keyboard
        )
        return EDIT_GET_NEW_CATEGORY

    if field == 'timestamp':
        await query.edit_message_text(
            t("history.edit_ask_new_date", context)
        )
        return EDIT_GET_NEW_DATE

    if field == 'currency':
        # Only show currency keyboard for dual-mode users
        mode, _ = _get_user_settings_for_tx(context)
        if mode == 'dual':
            await query.edit_message_text(
                t("history.edit_ask_new_currency", context),
                reply_markup=keyboards.currency_keyboard(context)
            )
            return EDIT_GET_NEW_CURRENCY
        else:
            await context.bot.answer_callback_query(
                query.id,
                t("history.edit_no_currency_single", context),
                show_alert=True
            )
            return EDIT_CHOOSE_FIELD  # Stay on the same menu

    if field == 'amount':
        await query.edit_message_text(
            t("history.edit_ask_new_amount", context)
        )
    if field == 'description':
        await query.edit_message_text(
            t("history.edit_ask_new_desc", context)
        )

    return EDIT_GET_NEW_VALUE


@authenticate_user
async def edit_received_new_value(update: Update,
                                  context: ContextTypes.DEFAULT_TYPE):
    """Receives new text value (amount/desc) and saves."""
    field = context.user_data['edit_field']
    value = update.message.text

    if field == 'amount':
        try:
            # We don't use the currency parser here, just update the number
            float(value)
        except ValueError:
            await update.message.reply_text(
                t("history.edit_invalid_amount", context)
            )
            return EDIT_GET_NEW_VALUE

    context.user_data['edit_new_value'] = value
    return await save_updated_transaction(update, context)


@authenticate_user
async def edit_received_new_date(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    """Receives new date value and saves."""
    try:
        new_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        tx_datetime = datetime.combine(
            new_date, time(12, 0), tzinfo=PHNOM_PENH_TZ
        )
        context.user_data['edit_new_value'] = tx_datetime.isoformat()
        return await save_updated_transaction(update, context)
    except ValueError:
        await update.message.reply_text(
            t("history.edit_invalid_date", context)
        )
        return EDIT_GET_NEW_DATE


@authenticate_user
async def edit_received_new_currency(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
    """Receives new currency from button and saves."""
    query = update.callback_query
    await query.answer()
    currency = query.data.split('_')[1]

    context.user_data['edit_new_value'] = currency
    # Also update the accountName to match
    context.user_data['edit_extra_field'] = {
        "field": "accountName",
        "value": f"{currency} Account"
    }
    return await save_updated_transaction(update, context)


@authenticate_user
async def edit_received_new_category(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
    """Receives new category from button and saves."""
    query = update.callback_query
    await query.answer()
    category = query.data.split('_')[1]

    if category == 'other':
        await query.edit_message_text(
            t("tx.ask_custom_category", context)
        )
        return EDIT_GET_CUSTOM_CATEGORY

    context.user_data['edit_new_value'] = category
    return await save_updated_transaction(update, context)


@authenticate_user
async def edit_received_custom_category(update: Update,
                                        context: ContextTypes.DEFAULT_TYPE):
    """Receives new custom category text and saves."""
    category = update.message.text.strip().title()
    context.user_data['edit_new_value'] = category
    return await save_updated_transaction(update, context)


async def save_updated_transaction(update: Update,
                                   context: ContextTypes.DEFAULT_TYPE):
    """Final step: save the updated transaction field to the API."""
    jwt = context.user_data['jwt']
    tx_id = context.user_data['edit_tx_id']
    field = context.user_data['edit_field']
    value = context.user_data['edit_new_value']

    payload = {field: value}

    # Check if we also need to update accountName (from currency edit)
    if 'edit_extra_field' in context.user_data:
        extra = context.user_data['edit_extra_field']
        payload[extra['field']] = extra['value']

    response = api_client.update_transaction(tx_id, payload, jwt)

    message_interface = (update.callback_query.message if update.callback_query
                         else update.message)

    if response and response.get('message'):
        await message_interface.reply_text(
            t("history.edit_success", context),
            reply_markup=keyboards.main_menu_keyboard(context)
        )
    else:
        error = response.get('error', 'Unknown error')
        await message_interface.reply_text(
            t("history.edit_update_fail", context, error=error),
            reply_markup=keyboards.main_menu_keyboard(context)
        )

    # --- THIS IS THE FIX ---
    # Clear only conversation state, not auth state
    context.user_data.pop('edit_tx_id', None)
    context.user_data.pop('edit_field', None)
    context.user_data.pop('edit_new_value', None)
    context.user_data.pop('edit_tx_type', None)
    context.user_data.pop('edit_extra_field', None)
    # --- END FIX ---

    return ConversationHandler.END

# --- End of file ---