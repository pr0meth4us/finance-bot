# --- Start of new file: telegram_bot/handlers/search.py ---

import api_client
import keyboards
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from .common import cancel
from .helpers import format_summation_results
from decorators import restricted
from datetime import datetime
from zoneinfo import ZoneInfo

# Conversation states
(
    CHOOSE_PERIOD, GET_CUSTOM_START, GET_CUSTOM_END, CHOOSE_TYPE,
    GET_CATEGORIES, GET_KEYWORDS, GET_KEYWORD_LOGIC,
    CHOOSE_ACTION
) = range(8)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")

# --- Regex for buttons ---
SEARCH_ACTION_REGEX = '^(What type of search do you want to perform?)$' # Dummy for CHOOSE_ACTION
REPORT_PERIOD_REGEX = '^(Today|This Week|Last Week|This Month|Last Month|Custom Range|♾️ All Time)$'
SEARCH_TYPE_REGEX = '^(💸 Expense|💰 Income|🌐 All Types)$'
SKIP_CAT_REGEX = '^(⏩ Skip)$'
SKIP_KWD_REGEX = '^(⏩ Skip)$'
LOGIC_REGEX = '^(Must contain ALL \(AND\)|Contains ANY \(OR\))$'


@restricted
async def search_menu_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the search sub-menu and enters the conversation."""
    await update.message.reply_text(
        text="What type of search do you want to perform?",
        reply_markup=keyboards.search_menu_keyboard()
    )
    return CHOOSE_ACTION


@restricted
async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the search type choice ('manage' or 'sum') and moves to period selection."""
    command = update.message.text # /search_manage or /search_sum
    search_type = command.replace('/search_', '') # 'manage' or 'sum'
    context.user_data['search_type'] = search_type
    context.user_data['search_params'] = {}

    await update.message.reply_text(
        "🔎 Advanced Search\n\nFirst, select a time period for the search.",
        reply_markup=keyboards.report_period_keyboard(is_search=True)
    )
    return CHOOSE_PERIOD


@restricted
async def received_period_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the period choice and asks for transaction type."""
    period_text = update.message.text

    period_map = {
        "Today": "today",
        "This Week": "this_week",
        "Last Week": "last_week",
        "This Month": "this_month",
        "Last Month": "last_month",
        "Custom Range": "custom",
        "♾️ All Time": "all_time"
    }

    period = period_map.get(period_text)
    if not period:
        await update.message.reply_text("Invalid choice.", reply_markup=keyboards.report_period_keyboard(is_search=True))
        return CHOOSE_PERIOD

    if period == "custom":
        await update.message.reply_text("Please enter the start date (YYYY-MM-DD):", reply_markup=keyboards.HIDE_KEYBOARD)
        return GET_CUSTOM_START
    elif period != "all_time":
        context.user_data['search_params']['period'] = period

    await update.message.reply_text(
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
    type_text = update.message.text

    type_map = {
        "💸 Expense": "expense",
        "💰 Income": "income",
        "🌐 All Types": "all"
    }

    tx_type = type_map.get(type_text)
    if not tx_type:
        await update.message.reply_text("Invalid choice.", reply_markup=keyboards.search_type_keyboard())
        return CHOOSE_TYPE

    if tx_type != 'all':
        context.user_data['search_params']['transaction_type'] = tx_type

    await update.message.reply_text(
        "Enter the categories you want to include, separated by a comma (e.g., Food, Drink).\n\nOr press Skip to include all categories.",
        reply_markup=keyboards.skip_keyboard()
    )
    return GET_CATEGORIES


@restricted
async def received_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives categories and asks for keywords."""
    message_text = "Enter keywords to search for in the description, separated by a comma (e.g., coffee, lunch).\n\nOr press Skip to not filter by keywords."

    if update.message.text == '⏩ Skip':
        pass # Do nothing, just move to next step
    else:  # User sent text
        categories = [c.strip() for c in update.message.text.split(',')]
        context.user_data['search_params']['categories'] = categories

    await update.message.reply_text(message_text, reply_markup=keyboards.skip_keyboard())
    return GET_KEYWORDS


@restricted
async def received_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives keywords and either asks for logic or executes the search."""
    if update.message.text == '⏩ Skip':
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


@restricted
async def received_keyword_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the keyword logic and executes the search."""
    logic_text = update.message.text
    if logic_text == "Must contain ALL (AND)":
        logic = 'AND'
    elif logic_text == "Contains ANY (OR)":
        logic = 'OR'
    else:
        await update.message.reply_text("Invalid choice.", reply_markup=keyboards.search_keyword_logic_keyboard())
        return GET_KEYWORD_LOGIC

    context.user_data['search_params']['keyword_logic'] = logic.upper()
    return await execute_search(update, context)


async def execute_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Executes the correct search type and displays results."""
    params = context.user_data.get('search_params', {})
    search_type = context.user_data.get('search_type')

    message_to_edit = await update.message.reply_text("🔎 searching...", reply_markup=keyboards.main_menu_keyboard())

    if search_type == 'manage':
        results = api_client.search_transactions_for_management(params)
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
            # This MUST be an InlineKeyboard
            await message_to_edit.edit_text(text=text, parse_mode='HTML',
                                            reply_markup=keyboards.manage_tx_keyboard(tx['_id']))
        else:
            text = f"Found {len(results)} matching transactions. Select one to manage:"
            # This MUST be an InlineKeyboard
            await message_to_edit.edit_text(text=text,
                                            reply_markup=keyboards.history_keyboard(results, is_search_result=True))

    elif search_type == 'sum':
        results = api_client.sum_transactions_for_analytics(params)
        response_text = format_summation_results(params, results)
        await message_to_edit.edit_text(response_text, parse_mode='HTML', reply_markup=keyboards.main_menu_keyboard())

    context.user_data.clear()
    return ConversationHandler.END