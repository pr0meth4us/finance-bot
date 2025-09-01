from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import keyboards
import api_client
from datetime import datetime, timedelta
from decorators import restricted  # Import our new security decorator

# --- Conversation States ---
AMOUNT, CURRENCY, CATEGORY, CUSTOM_CATEGORY, ASK_REMARK, REMARK = range(6)
NEW_RATE = range(6, 7)
IOU_PERSON, IOU_AMOUNT, IOU_CURRENCY = range(7, 10)
REPAY_AMOUNT = range(10, 11)
SETBALANCE_ACCOUNT, SETBALANCE_AMOUNT = range(11, 13)


# --- Helper Function ---
def format_summary_message(summary_data):
    """Formats the summary data into a readable string with separated currencies for debts."""
    if not summary_data:
        return ""

    khr_bal = summary_data.get('balances', {}).get('KHR', 0)
    usd_bal = summary_data.get('balances', {}).get('USD', 0)
    balance_text = f"💵 {usd_bal:,.2f} USD\n៛ {khr_bal:,.0f} KHR"

    owed_to_you_data = summary_data.get('debts_owed_to_you', [])
    owed_to_you_usd = next((item['total'] for item in owed_to_you_data if item['_id'] == 'USD'), 0)
    owed_to_you_khr = next((item['total'] for item in owed_to_you_data if item['_id'] == 'KHR'), 0)
    owed_to_you_text = f"    💵 {owed_to_you_usd:,.2f} USD\n    ៛ {owed_to_you_khr:,.0f} KHR"

    owed_by_you_data = summary_data.get('debts_owed_by_you', [])
    owed_by_you_usd = next((item['total'] for item in owed_by_you_data if item['_id'] == 'USD'), 0)
    owed_by_you_khr = next((item['total'] for item in owed_by_you_data if item['_id'] == 'KHR'), 0)
    owed_by_you_text = f"    💵 {owed_by_you_usd:,.2f} USD\n    ៛ {owed_by_you_khr:,.0f} KHR"

    return (
        f"\n\n--- Your Current Status ---\n"
        f"<b>Balances:</b>\n{balance_text}\n\n"
        f"<b>Debts:</b>\n"
        f"➡️ <b>You are owed:</b>\n{owed_to_you_text}\n"
        f"⬅️ <b>You owe:</b>\n{owed_by_you_text}"
    )


# --- Main Commands & Callbacks ---
@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main menu and forcibly ends any active conversation."""
    text = "Welcome to your Personal Finance Assistant!"
    keyboard = keyboards.main_menu_keyboard()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)

    return ConversationHandler.END


# --- Report Generation ---
@restricted
async def report_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the menu for selecting a report period."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "What period would you like a report for?",
        reply_markup=keyboards.report_period_keyboard()
    )


@restricted
async def generate_report_for_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and sends the analytics chart for the selected period."""
    query = update.callback_query
    await query.answer()
    period = query.data.split('_')[-1]

    today = datetime.utcnow().date()
    start_date, end_date = None, None

    if period == "today":
        start_date = end_date = today
    elif period == "this_week":
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == "last_week":
        end_date = today - timedelta(days=today.weekday() + 1)
        start_date = end_date - timedelta(days=6)
    elif period == "this_month":
        start_date = today.replace(day=1)
        next_month_first_day = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month_first_day - timedelta(days=1)

    if start_date and end_date:
        await query.edit_message_text(
            f"📈 Generating your report for {start_date.strftime('%b %d')} to {end_date.strftime('%b %d')}...")
        chart = api_client.get_chart(start_date, end_date)
        await query.message.delete()

        if chart:
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=chart)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Report sent! What's next?",
                reply_markup=keyboards.main_menu_keyboard()
            )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Could not generate report. No data found for this period.",
                reply_markup=keyboards.main_menu_keyboard()
            )


# --- Rate Update Conversation ---
@restricted
async def update_rate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation to update the exchange rate."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please enter the new exchange rate for 1 USD to KHR (e.g., 4100).")
    return NEW_RATE


async def received_new_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and saves the new exchange rate."""
    try:
        new_rate = float(update.message.text)
        response = api_client.update_exchange_rate(new_rate)
        if response:
            await update.message.reply_text(f"✅ {response['message']}", reply_markup=keyboards.main_menu_keyboard())
        else:
            await update.message.reply_text("❌ Failed to update the rate.", reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END
    except (ValueError, TypeError):
        await update.message.reply_text("Invalid number. Please enter a valid rate (e.g., 4100).")
        return NEW_RATE


# --- Transaction History & Management ---
@restricted
async def history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays a list of recent transactions to manage."""
    query = update.callback_query
    await query.answer()
    transactions = api_client.get_recent_transactions()
    if not transactions:
        await query.edit_message_text("No recent transactions found.", reply_markup=keyboards.main_menu_keyboard())
        return

    await query.edit_message_text(
        "Select a transaction to manage:",
        reply_markup=keyboards.history_keyboard(transactions)
    )


@restricted
async def manage_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows options for a selected transaction."""
    query = update.callback_query
    await query.answer()
    tx_id = query.data.split('_')[-1]
    text = f"Managing Transaction ID: ...{tx_id[-6:]}"
    await query.edit_message_text(text, reply_markup=keyboards.manage_tx_keyboard(tx_id))


@restricted
async def delete_transaction_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks for confirmation before deleting a transaction."""
    query = update.callback_query
    await query.answer()
    tx_id = query.data.split('_')[-1]
    await query.edit_message_text(
        "⚠️ Are you sure you want to delete this transaction?",
        reply_markup=keyboards.confirm_delete_keyboard(tx_id)
    )


@restricted
async def delete_transaction_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deletes the transaction after confirmation."""
    query = update.callback_query
    await query.answer()
    tx_id = query.data.split('_')[-1]
    success = api_client.delete_transaction(tx_id)
    if success:
        await query.edit_message_text("🗑️ Transaction successfully deleted.")
    else:
        await query.edit_message_text("❌ Error: Could not delete transaction.")

    transactions = api_client.get_recent_transactions()
    await query.message.reply_text(
        "Here is the updated history:",
        reply_markup=keyboards.history_keyboard(transactions)
    )


# --- IOU / Debt Management ---
@restricted
async def iou_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the IOU management menu."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🤝 Let's manage your IOUs.", reply_markup=keyboards.iou_menu_keyboard())


@restricted
async def iou_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a list of all open debts."""
    query = update.callback_query
    await query.answer()
    debts = api_client.get_open_debts()
    if not debts:
        await query.edit_message_text("You have no open debts! 👍", reply_markup=keyboards.iou_menu_keyboard())
        return

    text = "Select a debt to view details or record a repayment:"
    await query.edit_message_text(text, reply_markup=keyboards.iou_list_keyboard(debts))


@restricted
async def iou_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows details for a single debt."""
    query = update.callback_query
    await query.answer()
    debt_id = query.data.split('_')[-1]

    debt = api_client.get_debt_details(debt_id)
    if not debt:
        await query.edit_message_text("❌ Error: Could not find this debt.", reply_markup=keyboards.iou_menu_keyboard())
        return

    direction = "Owes you" if debt['type'] == 'lent' else "You owe"

    text = (
        f"<b>Debt Details:</b>\n"
        f"<b>Person:</b> {debt['person']} ({direction})\n"
        f"<b>Original Amount:</b> {debt.get('originalAmount', 0):,.2f} {debt.get('currency', '')}\n"
        f"<b>Remaining Balance:</b> {debt.get('remainingAmount', 0):,.2f} {debt.get('currency', '')}"
    )

    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=keyboards.iou_detail_keyboard(debt_id)
    )


# --- IOU Repayment Conversation ---
@restricted
async def repay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation to record a repayment."""
    query = update.callback_query
    await query.answer()
    debt_id = query.data.split('_')[-1]
    context.user_data['debt_id'] = debt_id

    await query.edit_message_text("How much was repaid?")
    return REPAY_AMOUNT


async def received_repayment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and saves the repayment amount."""
    try:
        amount = float(update.message.text)
        debt_id = context.user_data['debt_id']

        response = api_client.record_repayment(debt_id, amount)

        if response and 'remainingAmount' in response:
            remaining = response['remainingAmount']
            base_text = f"✅ Repayment of {amount:,.2f} recorded. The remaining balance is now {remaining:,.2f}."
            if remaining <= 0:
                base_text = "✅ Repayment recorded. This debt is now fully settled!"
        else:
            base_text = "❌ Error recording repayment. The amount might be too high or the debt not found."

        summary_data = api_client.get_balance_summary()
        summary_text = format_summary_message(summary_data)

        await update.message.reply_text(
            base_text + summary_text,
            parse_mode='HTML',
            reply_markup=keyboards.main_menu_keyboard()
        )

    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid number for the repayment amount.")
        return REPAY_AMOUNT

    context.user_data.clear()
    return ConversationHandler.END


# --- IOU Add Conversation ---
@restricted
async def iou_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation to add a new IOU."""
    query = update.callback_query
    await query.answer()
    context.user_data['iou_type'] = 'lent' if query.data == 'iou_lent' else 'borrowed'

    prompt = "Who did you lend money to?" if context.user_data[
                                                 'iou_type'] == 'lent' else "Who did you borrow money from?"
    await query.edit_message_text(prompt)
    return IOU_PERSON


async def iou_received_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['iou_person'] = update.message.text
    await update.message.reply_text("How much?")
    return IOU_AMOUNT


async def iou_received_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['iou_amount'] = float(update.message.text)
        await update.message.reply_text("Which currency?", reply_markup=keyboards.currency_keyboard())
        return IOU_CURRENCY
    except ValueError:
        await update.message.reply_text("Please enter a valid number for the amount.")
        return IOU_AMOUNT


async def iou_received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves a new IOU, then fetches and displays the summary."""
    query = update.callback_query
    await query.answer()
    context.user_data['iou_currency'] = query.data.split('_')[1]

    debt_data = {
        "type": context.user_data['iou_type'],
        "person": context.user_data['iou_person'],
        "amount": context.user_data['iou_amount'],
        "currency": context.user_data['iou_currency']
    }
    response = api_client.add_debt(debt_data)

    base_text = "✅ Debt successfully recorded!" if response else "❌ Failed to record debt."
    summary_data = api_client.get_balance_summary()
    summary_text = format_summary_message(summary_data)

    await query.edit_message_text(
        base_text + summary_text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard()
    )

    context.user_data.clear()
    return ConversationHandler.END


# --- Set Initial Balance Conversation ---
@restricted
async def set_balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation to set an initial balance."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Which account do you want to set the balance for?",
        reply_markup=keyboards.set_balance_account_keyboard()
    )
    return SETBALANCE_ACCOUNT


async def received_balance_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the account choice and asks for the amount."""
    query = update.callback_query
    await query.answer()
    currency = query.data.split('_')[-1]
    context.user_data['currency'] = currency
    context.user_data['accountName'] = "USD Account" if currency == "USD" else "KHR Account"

    await query.edit_message_text(f"What is the total current balance for your {currency} Account?")
    return SETBALANCE_AMOUNT


async def received_balance_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the amount and creates the 'Initial Balance' transaction."""
    try:
        amount = float(update.message.text)

        tx_data = {
            "type": "income",
            "amount": amount,
            "currency": context.user_data['currency'],
            "accountName": context.user_data['accountName'],
            "categoryId": "Initial Balance",
            "description": "Starting balance set by user"
        }

        api_client.add_transaction(tx_data)

        base_text = f"✅ Initial balance of {amount:,.2f} {context.user_data['currency']} set successfully!"

        summary_data = api_client.get_balance_summary()
        summary_text = format_summary_message(summary_data)

        await update.message.reply_text(
            base_text + summary_text,
            parse_mode='HTML',
            reply_markup=keyboards.main_menu_keyboard()
        )

        context.user_data.clear()
        return ConversationHandler.END

    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid number for the balance.")
        return SETBALANCE_AMOUNT


# --- Add Transaction Conversation ---
@restricted
async def add_transaction_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation to add an expense or income."""
    query = update.callback_query
    await query.answer()
    context.user_data['type'] = 'expense' if query.data == 'add_expense' else 'income'
    emoji = "💸" if context.user_data['type'] == 'expense' else "💰"
    await query.edit_message_text(f"{emoji} Enter the amount:")
    return AMOUNT


async def received_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the transaction amount."""
    try:
        context.user_data['amount'] = float(update.message.text)
        await update.message.reply_text("Which currency?", reply_markup=keyboards.currency_keyboard())
        return CURRENCY
    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return AMOUNT


async def received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the currency and shows the correct category keyboard."""
    query = update.callback_query
    await query.answer()
    currency = query.data.split('_')[1]
    context.user_data['currency'] = currency
    context.user_data['accountName'] = "USD Account" if currency == "USD" else "KHR Account"

    if context.user_data.get('type') == 'income':
        keyboard = keyboards.income_categories_keyboard()
    else:
        keyboard = keyboards.expense_categories_keyboard()

    await query.edit_message_text("Which category?", reply_markup=keyboard)
    return CATEGORY


async def received_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives a predefined category or triggers the custom category flow."""
    query = update.callback_query
    await query.answer()
    category_choice = query.data.split('_')[1]

    if category_choice == 'other':
        await query.edit_message_text("Please type your custom category name (e.g., Side Project, Freelance).")
        return CUSTOM_CATEGORY
    else:
        context.user_data['categoryId'] = category_choice
        await query.edit_message_text(
            "Great. Would you like to add a remark/description?",
            reply_markup=keyboards.ask_remark_keyboard()
        )
        return ASK_REMARK


async def received_custom_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives a manually typed custom category."""
    context.user_data['categoryId'] = update.message.text
    await update.message.reply_text(
        "Great. Would you like to add a remark/description?",
        reply_markup=keyboards.ask_remark_keyboard()
    )
    return ASK_REMARK


async def ask_remark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks if the user wants to add a remark, or skips it."""
    query = update.callback_query
    await query.answer()
    choice = query.data.split('_')[1]

    if choice == 'yes':
        await query.edit_message_text("Please type your remark.")
        return REMARK
    else:  # User chose 'no' / skip
        context.user_data['description'] = ''
        return await save_transaction_and_end(update, context)


async def received_remark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the optional remark text."""
    context.user_data['description'] = update.message.text
    return await save_transaction_and_end(update, context)


async def save_transaction_and_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves transaction, then fetches and displays the summary."""
    response = api_client.add_transaction(context.user_data)
    message_to_use = update.callback_query.message if update.callback_query else update.message

    base_text = "✅ Transaction recorded successfully!" if response else "❌ Failed to record transaction."

    summary_data = api_client.get_balance_summary()
    summary_text = format_summary_message(summary_data)

    await message_to_use.reply_text(
        base_text + summary_text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard()
    )

    if update.callback_query:
        await update.callback_query.message.delete()

    context.user_data.clear()
    return ConversationHandler.END


# --- Universal Cancel ---
@restricted
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any active conversation."""
    if update.message:
        await update.message.reply_text("Operation cancelled.", reply_markup=keyboards.main_menu_keyboard())
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Operation cancelled.",
                                                      reply_markup=keyboards.main_menu_keyboard())

    context.user_data.clear()
    return ConversationHandler.END


# --- Build Conversation Handlers ---
tx_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(add_transaction_start, pattern='^(add_expense|add_income)$')],
    states={
        AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_amount)],
        CURRENCY: [CallbackQueryHandler(received_currency, pattern='^curr_')],
        CATEGORY: [CallbackQueryHandler(received_category, pattern='^cat_')],
        CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_custom_category)],
        ASK_REMARK: [CallbackQueryHandler(ask_remark, pattern='^remark_')],
        REMARK: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_remark)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

rate_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(update_rate_start, pattern='^update_rate$')],
    states={NEW_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_new_rate)]},
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

iou_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(iou_start, pattern='^(iou_lent|iou_borrowed)$')],
    states={
        IOU_PERSON: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_person)],
        IOU_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_amount)],
        IOU_CURRENCY: [CallbackQueryHandler(iou_received_currency, pattern='^curr_')],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

repay_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(repay_start, pattern='^repay_start_')],
    states={
        REPAY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_repayment_amount)]
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

set_balance_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(set_balance_start, pattern='^set_balance_start$')],
    states={
        SETBALANCE_ACCOUNT: [CallbackQueryHandler(received_balance_account, pattern='^set_balance_')],
        SETBALANCE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_balance_amount)]
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)