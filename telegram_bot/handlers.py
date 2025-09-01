from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import keyboards      # * FIX: Changed from 'from . import keyboards, api_client' *
import api_client     # * FIX: Changed from 'from . import keyboards, api_client' *

# --- Conversation States ---
AMOUNT, CURRENCY, CATEGORY, CUSTOM_CATEGORY, ASK_REMARK, REMARK = range(6)
NEW_RATE = range(6, 7)
IOU_PERSON, IOU_AMOUNT, IOU_CURRENCY = range(7, 10)

# --- Main Commands & Callbacks ---
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

async def get_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and sends the analytics chart."""
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("📈 Generating your report...")
    chart = api_client.get_chart()
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
            text="Could not generate report. No data found.",
            reply_markup=keyboards.main_menu_keyboard()
        )

# --- Rate Update Conversation ---
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

async def manage_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows options for a selected transaction."""
    query = update.callback_query
    await query.answer()
    tx_id = query.data.split('_')[-1]
    text = f"Managing Transaction ID: ...{tx_id[-6:]}"
    await query.edit_message_text(text, reply_markup=keyboards.manage_tx_keyboard(tx_id))

async def delete_transaction_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks for confirmation before deleting a transaction."""
    query = update.callback_query
    await query.answer()
    tx_id = query.data.split('_')[-1]
    await query.edit_message_text(
        "⚠️ Are you sure you want to delete this transaction?",
        reply_markup=keyboards.confirm_delete_keyboard(tx_id)
    )

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
async def iou_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the IOU management menu."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🤝 Let's manage your IOUs.", reply_markup=keyboards.iou_menu_keyboard())

async def iou_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a list of all open debts."""
    query = update.callback_query
    await query.answer()
    debts = api_client.get_open_debts()
    if not debts:
        await query.edit_message_text("You have no open debts! 👍", reply_markup=keyboards.iou_menu_keyboard())
        return

    text = "Click on a debt to mark it as settled:"
    await query.edit_message_text(text, reply_markup=keyboards.iou_list_keyboard(debts))

async def iou_settle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Marks a debt as settled and creates a corresponding transaction."""
    query = update.callback_query
    await query.answer()
    debt_id = query.data.split('_')[-1]

    response = api_client.settle_debt(debt_id)
    if response:
        await query.edit_message_text(f"✅ {response['message']}")
    else:
        await query.edit_message_text("❌ Error settling debt.")

    debts = api_client.get_open_debts()
    if not debts:
        await query.message.reply_text("All debts are now settled! 👍", reply_markup=keyboards.iou_menu_keyboard())
    else:
        await query.message.reply_text("Here is the updated list of open debts:", reply_markup=keyboards.iou_list_keyboard(debts))

# --- IOU Add Conversation ---
async def iou_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation to add a new IOU."""
    query = update.callback_query
    await query.answer()
    context.user_data['iou_type'] = 'lent' if query.data == 'iou_lent' else 'borrowed'

    prompt = "Who did you lend money to?" if context.user_data['iou_type'] == 'lent' else "Who did you borrow money from?"
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
    if response:
        await query.edit_message_text("✅ Debt successfully recorded!", reply_markup=keyboards.main_menu_keyboard())
    else:
        await query.edit_message_text("❌ Failed to record debt.", reply_markup=keyboards.main_menu_keyboard())

    context.user_data.clear()
    return ConversationHandler.END

# --- Add Transaction Conversation ---
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
    """Receives the currency and automatically determines the account."""
    query = update.callback_query
    await query.answer()
    currency = query.data.split('_')[1]
    context.user_data['currency'] = currency
    context.user_data['accountName'] = "USD Account" if currency == "USD" else "KHR Account"

    await query.edit_message_text("Which category?", reply_markup=keyboards.categories_keyboard())
    return CATEGORY

async def received_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives a predefined category or triggers the custom category flow."""
    query = update.callback_query
    await query.answer()
    category_choice = query.data.split('_')[1]

    if category_choice == 'other':
        await query.edit_message_text("Please type your custom category name (e.g., Coffee, Books).")
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
    else: # User chose 'no' / skip
        context.user_data['description'] = ''
        return await save_transaction_and_end(update, context)

async def received_remark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the optional remark text."""
    context.user_data['description'] = update.message.text
    return await save_transaction_and_end(update, context)

async def save_transaction_and_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """A helper function to save the transaction data and end the conversation."""
    response = api_client.add_transaction(context.user_data)

    message_to_use = update.callback_query.message if update.callback_query else update.message

    if response:
        await message_to_use.reply_text("✅ Transaction recorded successfully!", reply_markup=keyboards.main_menu_keyboard())
    else:
        await message_to_use.reply_text("❌ Failed to record transaction.", reply_markup=keyboards.main_menu_keyboard())

    if update.callback_query:
        await update.callback_query.message.delete()

    context.user_data.clear()
    return ConversationHandler.END

# --- Universal Cancel ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any active conversation."""
    if update.message:
        await update.message.reply_text("Operation cancelled.", reply_markup=keyboards.main_menu_keyboard())
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Operation cancelled.", reply_markup=keyboards.main_menu_keyboard())

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