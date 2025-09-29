# --- Start of new file: telegram_bot/handlers/search.py ---

import api_client
import keyboards
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from .common import cancel
from .helpers import format_search_results
from decorators import restricted
from datetime import datetime

# Conversation states
(
    CHOOSE_PERIOD, GET_CUSTOM_START, GET_CUSTOM_END, CHOOSE_TYPE,
    GET_CATEGORIES, GET_KEYWORDS, GET_KEYWORD_LOGIC
) = range(7)


@restricted
async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the advanced search conversation."""
    query = update.callback_query
    await query.answer()
    context.user_data['search_params'] = {}
    await query.edit_message_text(
        "🔎 Advanced Search\n\nFirst, select a time period for the search.",
        reply_markup=keyboards.report_period_keyboard(is_search=True)
    )
    return CHOOSE_PERIOD


@restricted
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


@restricted
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


@restricted
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


@restricted
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


@restricted
async def received_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives categories and asks for keywords."""
    message_text = "Enter keywords to search for in the description, separated by a comma (e.g., coffee, lunch).\n\nOr press Skip to not filter by keywords."
    if update.callback_query: # User pressed skip
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message_text, reply_markup=keyboards.skip_keyboard('search_skip_keywords'))
    else: # User sent text
        categories = [c.strip() for c in update.message.text.split(',')]
        context.user_data['search_params']['categories'] = categories
        await update.message.reply_text(message_text, reply_markup=keyboards.skip_keyboard('search_skip_keywords'))

    return GET_KEYWORDS


@restricted
async def received_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives keywords and either asks for logic or executes the search."""
    if update.callback_query: # User pressed skip
        await update.callback_query.answer()
        # No keywords, so execute search directly
        return await execute_search(update, context)

    # User sent text
    keywords = [k.strip() for k in update.message.text.split(',')]
    context.user_data['search_params']['keywords'] = keywords

    # If there's more than one keyword, ask for the logic (AND/OR)
    if len(keywords) > 1:
        await update.message.reply_text(
            "Should the description contain ALL of these keywords (AND) or ANY of them (OR)?",
            reply_markup=keyboards.search_keyword_logic_keyboard()
        )
        return GET_KEYWORD_LOGIC

    # Only one keyword, default to OR logic and execute search
    context.user_data['search_params']['keyword_logic'] = 'OR'
    return await execute_search(update, context)


@restricted
async def received_keyword_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the keyword logic and executes the search."""
    query = update.callback_query
    await query.answer()
    logic = query.data.replace('search_logic_', '')
    context.user_data['search_params']['keyword_logic'] = logic.upper()
    return await execute_search(update, context)


async def execute_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Executes the search via API and displays the result."""
    params = context.user_data.get('search_params', {})
    message = update.message or update.callback_query.message
    await message.reply_text(" searching...")

    # Call API
    results = api_client.search_transactions(params)

    # Format and send results
    response_text = format_search_results(params, results)
    await message.reply_text(
        response_text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard()
    )

    context.user_data.clear()
    return ConversationHandler.END