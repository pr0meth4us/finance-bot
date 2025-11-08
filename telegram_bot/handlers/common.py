# --- Start of file: telegram_bot/handlers/common.py ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import keyboards
import api_client
from decorators import authenticate_user # <-- MODIFIED: Import new decorator
from .helpers import format_summary_message

# --- Main Commands & Callbacks ---
@authenticate_user # <-- MODIFIED: Use new decorator
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main menu and forcibly ends any active conversation."""

    # --- MODIFICATION: Get user_id from the profile cached by the decorator ---
    user_profile = context.user_data['user_profile']
    user_id = user_profile['_id']
    user_name = user_profile.get('name', 'User')
    # ---

    text = f"Welcome, {user_name}!" # <-- MODIFIED: Personalized welcome
    keyboard = keyboards.main_menu_keyboard()
    chat_id = update.effective_chat.id

    if update.callback_query:
        await update.callback_query.answer()
        summary_data = api_client.get_detailed_summary(user_id) # <-- MODIFIED: Pass user_id
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
        summary_data = api_client.get_detailed_summary(user_id) # <-- MODIFIED: Pass user_id
        summary_text = format_summary_message(summary_data)
        await context.bot.send_message(
            chat_id=chat_id,
            text=text + summary_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )

    return ConversationHandler.END


@authenticate_user # <-- MODIFIED: Use new decorator
async def quick_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays a quick summary of balances and debts."""
    query = update.callback_query
    await query.answer("Fetching summary...")

    # --- MODIFICATION: Get user_id from context ---
    user_id = context.user_data['user_profile']['_id']
    # ---

    summary_data = api_client.get_detailed_summary(user_id) # <-- MODIFIED: Pass user_id
    summary_text = format_summary_message(summary_data)
    text = f"🔍 Here is your quick summary:{summary_text}"

    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard()
    )


# No decorator needed for cancel, as it should work even if not authenticated
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    """Cancels any active conversation."""
    message = "Operation cancelled."
    keyboard = keyboards.main_menu_keyboard()
    chat_id = update.effective_chat.id

    if update.callback_query:
        # If cancelled from a button press, edit the message
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text=message, reply_markup=keyboard)
        except Exception:
            # Failsafe if message is old, just send a new one
            await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=keyboard)
    else:
        # If cancelled from a /cancel command, send a new message
        await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=keyboard)

    context.user_data.clear()
    return ConversationHandler.END
# --- End of modified file ---