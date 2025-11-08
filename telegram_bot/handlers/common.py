# --- Start of modified file: telegram_bot/handlers/common.py ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import keyboards
import api_client
from decorators import authenticate_user
from .helpers import format_summary_message
from ..utils.i18n import t


@authenticate_user
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main menu and forcibly ends any active conversation."""

    user_profile = context.user_data['user_profile']
    user_id = user_profile['_id']
    user_name = user_profile.get('name', 'User')

    text = t("common.welcome", context, name=user_name)
    keyboard = keyboards.main_menu_keyboard(context)
    chat_id = update.effective_chat.id

    summary_data = api_client.get_detailed_summary(user_id)
    summary_text = format_summary_message(summary_data, context)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                text + summary_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except Exception:
            pass
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text + summary_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )

    return ConversationHandler.END


@authenticate_user
async def quick_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays a quick summary of balances and debts."""
    query = update.callback_query
    await query.answer("Fetching summary...")

    user_id = context.user_data['user_profile']['_id']

    summary_data = api_client.get_detailed_summary(user_id)
    summary_text = format_summary_message(summary_data, context)
    text = t("common.quick_check_header", context) + summary_text

    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard(context)
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any active conversation."""
    message = t("common.cancel", context)
    keyboard = keyboards.main_menu_keyboard(context)
    chat_id = update.effective_chat.id

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                text=message, reply_markup=keyboard
            )
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id, text=message, reply_markup=keyboard
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id, text=message, reply_markup=keyboard
        )

    context.user_data.clear()
    return ConversationHandler.END
# --- End of modified file ---