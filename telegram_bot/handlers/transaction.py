# --- Start of file: telegram_bot/handlers/transaction.py ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import keyboards
import api_client
from decorators import restricted
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from .helpers import format_summary_message

# Conversation states
(
    AMOUNT, CURRENCY, CATEGORY, CUSTOM_CATEGORY, ASK_REMARK, REMARK,
    FORGOT_DATE, FORGOT_CUSTOM_DATE, FORGOT_TYPE,
    EDIT_CHOOSE_FIELD, EDIT_GET_NEW_VALUE, EDIT_GET_NEW_CATEGORY
) = range(12)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")

# --- Add Transaction & Forgot Log (Shared Logic) ---
@restricted
async def add_transaction_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data['type'] = 'expense' if query.data == 'add_expense' else 'income'
    emoji = "💸" if context.user_data['type'] == 'expense' else "💰"
    await query.message.reply_text(f"{emoji} Enter the amount:")
    return AMOUNT

@restricted
async def forgot_log_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.message.reply_text("Which day did you forget to log?", reply_markup=keyboards.forgot_day_keyboard())
    return FORGOT_DATE

async def received_forgot_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split('_')[-1]
    if choice == 'custom':
        await query.message.reply_text("Please enter the date in YYYY-MM-DD format.")
        return FORGOT_CUSTOM_DATE

    days_ago = int(choice)
    forgotten_date = datetime.now(PHNOM_PENH_TZ).date() - timedelta(days=days_ago)
    context.user_data['timestamp'] = datetime.combine(forgotten_date, time(12, 0), tzinfo=PHNOM_PENH_TZ).isoformat()
    await query.message.reply_text("Got it. Was it an expense or an income?", reply_markup=keyboards.forgot_type_keyboard())
    return FORGOT_TYPE

async def received_forgot_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        custom_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['timestamp'] = datetime.combine(custom_date, time(12, 0), tzinfo=PHNOM_PENH_TZ).isoformat()
        await update.message.reply_text("Got it. Was it an expense or an income?", reply_markup=keyboards.forgot_type_keyboard())
        return FORGOT_TYPE
    except ValueError:
        await update.message.reply_text("Invalid format. Please use YYYY-MM-DD.")
        return FORGOT_CUSTOM_DATE

async def received_forgot_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['type'] = query.data.split('_')[-1]
    await query.message.reply_text(f"Type: <b>{context.user_data['type'].capitalize()}</b>\n\nEnter the amount:", parse_mode='HTML')
    return AMOUNT

async def received_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        context.user_data['amount'] = amount

        if amount < 100:
            # Auto-select USD and skip to category selection
            currency = "USD"
            context.user_data['currency'] = currency
            context.user_data['accountName'] = "USD Account"
            keyboard = keyboards.income_categories_keyboard() if context.user_data.get('type') == 'income' else keyboards.expense_categories_keyboard()
            await update.message.reply_text(f"Amount: <b>{amount:,.2f} USD</b> (auto-selected)\n\nWhich category?", parse_mode='HTML', reply_markup=keyboard)
            return CATEGORY
        else:
            # Ask for currency as usual
            await update.message.reply_text("Which currency?", reply_markup=keyboards.currency_keyboard())
            return CURRENCY
    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return AMOUNT

async def received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    currency = query.data.split('_')[1]
    context.user_data['currency'] = currency
    context.user_data['accountName'] = "USD Account" if currency == "USD" else "KHR Account"
    keyboard = keyboards.income_categories_keyboard() if context.user_data.get('type') == 'income' else keyboards.expense_categories_keyboard()
    await query.message.reply_text(f"Currency: <b>{currency}</b>\n\nWhich category?", parse_mode='HTML', reply_markup=keyboard)
    return CATEGORY

async def received_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split('_')[1]
    if category == 'other':
        await query.message.reply_text("Please type your custom category name:")
        return CUSTOM_CATEGORY
    context.user_data['categoryId'] = category
    await query.message.reply_text(f"Category: <b>{category}</b>\n\nAdd a remark/description?", parse_mode='HTML', reply_markup=keyboards.ask_remark_keyboard())
    return ASK_REMARK

async def received_custom_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['categoryId'] = update.message.text.strip().title()
    await update.message.reply_text("Add a remark/description?", reply_markup=keyboards.ask_remark_keyboard())
    return ASK_REMARK

async def ask_remark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'remark_yes':
        await query.message.reply_text("Please type your remark.")
        return REMARK
    context.user_data['description'] = ''
    return await save_transaction_and_end(update, context)

async def received_remark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text.strip()
    return await save_transaction_and_end(update, context)

async def save_transaction_and_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = api_client.add_transaction(context.user_data)
    message = update.callback_query.message if update.callback_query else update.message
    base_text = "✅ Transaction recorded successfully!" if response else "❌ Failed to record transaction."
    summary_text = format_summary_message(api_client.get_detailed_summary())
    await message.reply_text(base_text + summary_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

# --- History & Management ---
@restricted
async def history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    transactions = api_client.get_recent_transactions()
    text = "Select a transaction to manage:"
    keyboard = keyboards.history_keyboard(transactions)
    if not transactions:
        text = "No recent transactions found."
        keyboard = keyboards.main_menu_keyboard()
    await query.edit_message_text(text=text, reply_markup=keyboard)

@restricted
async def manage_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tx_id = query.data.split('_')[-1]
    tx = api_client.get_transaction_details(tx_id)
    if not tx:
        await query.edit_message_text("Error: Could not fetch transaction details.", reply_markup=keyboards.main_menu_keyboard())
        return

    emoji = "⬇️ Expense" if tx['type'] == 'expense' else "⬆️ Income"
    date_str = datetime.fromisoformat(tx['timestamp'].replace('Z', '+00:00')).astimezone(PHNOM_PENH_TZ).strftime('%d %b %Y, %I:%M %p')
    amount_format = ",.0f" if tx['currency'] == 'KHR' else ",.2f"
    text = (
        f"<b>Transaction Details:</b>\n\n"
        f"<b>Type:</b> {emoji}\n"
        f"<b>Amount:</b> {tx['amount']:{amount_format}} {tx['currency']}\n"
        f"<b>Category:</b> {tx['categoryId']}\n"
        f"<b>Description:</b> {tx.get('description') or 'N/A'}\n"
        f"<b>Date:</b> {date_str}\n\n"
        "What would you like to do?"
    )
    await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=keyboards.manage_tx_keyboard(tx_id))

@restricted
async def delete_transaction_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tx_id = query.data.split('_')[-1]
    await query.edit_message_text("⚠️ Are you sure you want to delete this transaction?", reply_markup=keyboards.confirm_delete_keyboard(tx_id))

@restricted
async def delete_transaction_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Deleting...")
    tx_id = query.data.split('_')[-1]
    if api_client.delete_transaction(tx_id):
        await query.edit_message_text("🗑️ Transaction successfully deleted.")
        import asyncio
        await asyncio.sleep(1.5)
        await history_menu(update, context)
    else:
        await query.edit_message_text("❌ Error: Could not delete transaction.", reply_markup=keyboards.manage_tx_keyboard(tx_id))

# --- Edit Transaction Conversation ---
@restricted
async def edit_transaction_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tx_id = query.data.split('_')[-1]
    transaction = api_client.get_transaction_details(tx_id)
    if not transaction:
        await query.edit_message_text("❌ Error: Transaction not found.", reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END
    context.user_data.update({'edit_tx_id': tx_id, 'edit_tx_type': transaction.get('type')})
    await query.edit_message_text("Which field would you like to edit?", reply_markup=keyboards.edit_tx_options_keyboard(tx_id))
    return EDIT_CHOOSE_FIELD

async def edit_choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.split('_')[2]
    context.user_data['edit_tx_field'] = field
    if field == 'categoryId':
        tx_type = context.user_data.get('edit_tx_type')
        keyboard = keyboards.income_categories_keyboard() if tx_type == 'income' else keyboards.expense_categories_keyboard()
        await query.edit_message_text("Please select the new category:", reply_markup=keyboard)
        return EDIT_GET_NEW_CATEGORY
    prompts = {'amount': "Please enter the new amount:", 'description': "Please enter the new description:"}
    await query.edit_message_text(prompts[field])
    return EDIT_GET_NEW_VALUE

async def edit_received_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data.get('edit_tx_field')
    value = update.message.text
    if field == 'amount':
        try:
            value = float(value)
        except ValueError:
            await update.message.reply_text("Invalid amount. Please enter a valid number.")
            return EDIT_GET_NEW_VALUE
    context.user_data['edit_tx_new_value'] = value
    return await _update_transaction_and_confirm(update, context)

async def edit_received_new_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split('_')[1]
    if category == 'other':
        await query.edit_message_text("Editing to a custom category is not supported here. Please choose a standard one.")
        return EDIT_GET_NEW_CATEGORY
    context.user_data['edit_tx_new_value'] = category
    return await _update_transaction_and_confirm(update, context)

async def _update_transaction_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper to perform the API call and confirm to user."""
    tx_id = context.user_data.get('edit_tx_id')
    field = context.user_data.get('edit_tx_field')
    value = context.user_data.get('edit_tx_new_value')
    message = update.message or update.callback_query.message

    response = api_client.update_transaction(tx_id, {field: value})
    if response and 'error' not in response:
        summary_text = format_summary_message(api_client.get_detailed_summary())
        await message.reply_text(f"✅ Transaction successfully updated!{summary_text}", parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())
    else:
        error = response.get('error', 'Could not update transaction.') if response else 'Could not update.'
        await message.reply_text(f"❌ Error: {error}", reply_markup=keyboards.main_menu_keyboard())

    context.user_data.clear()
    return ConversationHandler.END