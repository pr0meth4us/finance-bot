# --- Start of file: telegram_bot/handlers/common.py ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import keyboards
import api_client
from decorators import restricted
from .helpers import format_summary_message

# --- Main Commands & Callbacks ---
@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main menu and forcibly ends any active conversation."""
    text = "Welcome to your Personal Finance Assistant!"
    keyboard = keyboards.main_menu_keyboard()
    chat_id = update.effective_chat.id

    if update.callback_query:
        await update.callback_query.answer()
        summary_data = api_client.get_detailed_summary()
        summary_text = format_summary_message(summary_data)
        try:
            await update.callback_query.edit_message_text(
                text + summary_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except Exception:
            pass
    else:
        summary_data = api_client.get_detailed_summary()
        summary_text = format_summary_message(summary_data)
        await context.bot.send_message(
            chat_id=chat_id,
            text=text + summary_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )

    return ConversationHandler.END


@restricted
async def quick_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays a quick summary of balances and debts."""
    query = update.callback_query
    await query.answer("Fetching summary...")

    summary_data = api_client.get_detailed_summary()
    summary_text = format_summary_message(summary_data)
    text = f"🔍 Here is your quick summary:{summary_text}"

    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard()
    )


@restricted
async def search_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the search sub-menu."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="What type of search do you want to perform?",
        reply_markup=keyboards.search_menu_keyboard()
    )

# --- NEW FUNCTION ---
@restricted
async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """A simple helper command to get the current chat's ID."""
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"This chat's ID is: `{chat_id}`", parse_mode='Markdown')


@restricted
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any active conversation."""
    message = "Operation cancelled."
    keyboard = keyboards.main_menu_keyboard()
    chat_id = update.effective_chat.id
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text=message, reply_markup=keyboard)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=keyboard)
    else:
        await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=keyboard)

    context.user_data.clear()
    return ConversationHandler.END