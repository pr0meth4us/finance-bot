# --- Start of new file: telegram_bot/handlers/search.py ---

import api_client
import keyboards
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from .common import cancel
from .helpers import format_summation_results
from decorators import authenticate_user # <-- MODIFICATION: Fix import
from datetime import datetime
from zoneinfo import ZoneInfo

# Conversation states
(
    CHOOSE_PERIOD, GET_CUSTOM_START, GET_CUSTOM_END, CHOOSE_TYPE,
    GET_CATEGORIES, GET_KEYWORDS, GET_KEYWORD_LOGIC,
    CHOOSE_ACTION
) = range(8)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")


@authenticate_user # <-- MODIFICATION
async def search_menu_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the search sub-menu and enters the conversation."""
    query = update.callback_query
    await query.answer()

    # --- MODIFICATION: Re-cache user_profile after clear() ---
    context.user_data.clear()
    context.user_data['user_profile'] = context.application.user_data[update.effective_user.id]['user_profile']
    # ---

    await query.edit_message_text(
        text="What type of search do you want to perform?",
        reply_markup=keyboards.search_menu_keyboard()
    )
    return CHOOSE_ACTION


@authenticate_user # <-- MODIFICATION
async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the search type choice ('manage' or 'sum') and moves to period selection."""
    query = update.callback_query
    await query.answer()

    search_type = query.data.replace('start_search_', '')
    context.user_data['search_type'] = search_type
    context.user_data['search_params'] = {}

    await query.edit_message_text(
        "🔎 Advanced Search\n\nFirst, select a time period for the search.",
        reply_markup=keyboards.report_period_keyboard(is_search=True)
    )
    return CHOOSE_PERIOD


@authenticate_user # <-- MODIFICATION
async def received_period_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the period choice and asks for transaction type."""
    query = update.callback_query
    await query.answer()
    period = query.data.replace('report_period_', '')

    if period == "custom":
        await query.edit_message_text("Please enter the start date (YYYY-MM-DD):")
        return GET_CUSTOM_START
    elif period != "all_time":
        context.user_data['search_params']['period'] = period

    await query.edit_message_text(
        "Which transaction type do you want to search?",
        reply_markup=keyboards.search_type_keyboard()
    )
    return CHOOSE_TYPE


@authenticate_user # <-- MODIFICATION
async def received_custom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and validates the custom start date."""
    try:
        start_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['search_params']['start_date'] = start_date.isoformat()
        await update.message.reply_text(
            f"Start date set to {start_date:%Y-%m-%d}.\nNow, please enter the end date (YYYY-MM-DD):")
        return GET_CUSTOM_END
    except ValueError:
        await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD.")
        return GET_CUSTOM_START


@authenticate_user # <-- MODIFICATION
async def received_custom_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives, validates end date, and asks for transaction type."""
    try:
        end_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        start_date_str = context.user_data['search_params'].get('start_date')
        if not start_date_str or end_date < datetime.fromisoformat(start_date_str).date():
            await update.message.reply_text("Invalid date range. End date cannot be before start date.")
            return GET_CUSTOM_END
        context.user_data['search_params']['end_date'] = end_date.isoformat()
        await update.message.reply_text(
            "Which transaction type do you want to search?",
            reply_markup=keyboards.search_type_keyboard()
        )
        return CHOOSE_TYPE
    except ValueError:
        await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD.")
        return GET_CUSTOM_END


@authenticate_user # <-- MODIFICATION
async def received_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the transaction type choice and asks for categories."""
    query = update.callback_query
    await query.answer()
    tx_type = query.data.replace('search_type_', '')
    if tx_type != 'all':
        context.user_data['search_params']['transaction_type'] = tx_type

    await query.edit_message_text(
        "Enter the categories you want to include, separated by a comma (e.g., Food, Drink).\n\nOr press Skip to include all categories.",
        reply_markup=keyboards.skip_keyboard('search_skip_categories')
    )
    return GET_CATEGORIES


@authenticate_user # <-- MODIFICATION
async def received_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives categories and asks for keywords."""
    message_text = "Enter keywords to search for in the description, separated by a comma (e.g., coffee, lunch).\n\nOr press Skip to not filter by keywords."
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message_text,
                                                      reply_markup=keyboards.skip_keyboard('search_skip_keywords'))
    else:
        categories = [c.strip() for c in update.message.text.split(',')]
        context.user_data['search_params']['categories'] = categories
        await update.message.reply_text(message_text, reply_markup=keyboards.skip_keyboard('search_skip_keywords'))

    return GET_KEYWORDS


@authenticate_user # <-- MODIFICATION
async def received_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives keywords and either asks for logic or executes the search."""
    if update.callback_query:
        await update.callback_query.answer()
        return await execute_search(update, context)

    keywords = [k.strip() for k in update.message.text.split(',')]
    context.user_data['search_params']['keywords'] = keywords

    if len(keywords) > 1:
        await update.message.reply_text(
            "Should the description contain ALL of these keywords (AND) or ANY of them (OR)?",
            reply_markup=keyboards.search_keyword_logic_keyboard()
        )
        return GET_KEYWORD_LOGIC

    context.user_data['search_params']['keyword_logic'] = 'OR'
    return await execute_search(update, context)


@authenticate_user # <-- MODIFICATION
async def received_keyword_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the keyword logic and executes the search."""
    query = update.callback_query
    await query.answer()
    logic = query.data.replace('search_logic_', '')
    context.user_data['search_params']['keyword_logic'] = logic.upper()
    return await execute_search(update, context)


async def execute_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Executes the correct search type and displays results by editing the message."""

    # --- MODIFICATION: Get user_id ---
    user_id = context.user_data['user_profile']['_id']
    # ---

    params = context.user_data.get('search_params', {})
    search_type = context.user_data.get('search_type')

    message_to_edit = None
    if update.callback_query:
        await update.callback_query.edit_message_text("🔎 searching...")
        message_to_edit = update.callback_query.message
    else:
        message_to_edit = await update.message.reply_text("🔎 searching...")

    if search_type == 'manage':
        results = api_client.search_transactions_for_management(params, user_id) # <-- MODIFICATION
        if not results:
            await message_to_edit.edit_text("No transactions found matching your criteria.",
                                            reply_markup=keyboards.main_menu_keyboard())
        elif len(results) == 1:
            tx = results[0]
            emoji = "⬇️ Expense" if tx['type'] == 'expense' else "⬆️ Income"
            date_str = datetime.fromisoformat(tx['timestamp'].replace('Z', '+00:00')).astimezone(
                PHNOM_PENH_TZ).strftime('%d %b %Y, %I:%M %p')
            amount_format = ",.0f" if tx['currency'] == 'KHR' else ",.2f"
            text = (
                f"Found 1 matching transaction:\n\n<b>Transaction Details:</b>\n"
                f"<b>Type:</b> {emoji}\n"
                f"<b>Amount:</b> {tx['amount']:{amount_format}} {tx['currency']}\n"
                f"<b>Category:</b> {tx['categoryId']}\n"
                f"<b>Description:</b> {tx.get('description') or 'N/A'}\n"
                f"<b>Date:</b> {date_str}"
            )
            await message_to_edit.edit_text(text=text, parse_mode='HTML',
                                            reply_markup=keyboards.manage_tx_keyboard(tx['_id']))
        else:
            text = f"Found {len(results)} matching transactions. Select one to manage:"
            await message_to_edit.edit_text(text=text,
                                            reply_markup=keyboards.history_keyboard(results, is_search_result=True))

    elif search_type == 'sum':
        results = api_client.sum_transactions_for_analytics(params, user_id) # <-- MODIFICATION
        response_text = format_summation_results(params, results)
        await message_to_edit.edit_text(response_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())

    context.user_data.clear()
    return ConversationHandler.END
# --- End of new file ---