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

    # This function is now only triggered by /start command or a fallback.
    # We always send a new message.
    summary_data = api_client.get_detailed_summary()
    summary_text = format_summary_message(summary_data)
    await context.bot.send_message(
        chat_id=chat_id,
        text=text + summary_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

    # If this was triggered by an inline button (e.g., from a dynamic menu)
    if update.callback_query:
        await update.callback_query.answer()
        # We still send a new message, but we also try to remove the old inline keyboard
        try:
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass # Message might be too old, doesn't matter

    return ConversationHandler.END


@restricted
async def quick_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays a quick summary of balances and debts."""
    summary_data = api_client.get_detailed_summary()
    summary_text = format_summary_message(summary_data)
    text = f"🔍 Here is your quick summary:{summary_text}"

    await update.message.reply_text(
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard()
    )


@restricted
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any active conversation."""
    message = "Operation cancelled."
    keyboard = keyboards.main_menu_keyboard()
    chat_id = update.effective_chat.id

    # If cancelled from a /cancel command
    await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=keyboard)

    context.user_data.clear()
    return ConversationHandler.END