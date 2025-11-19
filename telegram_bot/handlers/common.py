# telegram_bot/handlers/common.py

import telegram.error
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import keyboards
import api_client
from decorators import authenticate_user
from .helpers import format_summary_message
from utils.i18n import t


@authenticate_user
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays the main menu.
    This handler handles the UI response; onboarding logic is handled by the
    separate onboarding handler or the decorator checks.
    """
    profile = context.user_data['profile']
    jwt = context.user_data['jwt']

    lang = profile.get('settings', {}).get('language', 'en')
    user_name = profile.get('name_en', 'User')
    if lang == 'km' and profile.get('name_km'):
        user_name = profile.get('name_km')

    # Fetch summary
    summary_data = api_client.get_detailed_summary(jwt)
    summary_text = format_summary_message(summary_data, context)

    # --- UI FIX: Ensure spacing between Welcome and Summary ---
    welcome_text = t("common.welcome", context, name=user_name)

    # If summary exists, prepend newlines. If empty (new user), just show welcome.
    if summary_text:
        final_text = f"{welcome_text}\n\n{summary_text}"
    else:
        final_text = welcome_text
    # ---------------------------------------------------------

    keyboard = keyboards.main_menu_keyboard(context)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                final_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except telegram.error.BadRequest as e:
            if "Message is not modified" in str(e):
                pass
            else:
                raise e
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=final_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )

    return ConversationHandler.END


@authenticate_user
async def quick_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays a quick summary of balances and debts."""
    query = update.callback_query
    await query.answer("Fetching summary...")

    jwt = context.user_data['jwt']
    summary_data = api_client.get_detailed_summary(jwt)
    summary_text = format_summary_message(summary_data, context)

    # --- UI FIX: Ensure spacing here too ---
    header = t("common.quick_check_header", context)
    text = f"{header}\n{summary_text}"
    # ---------------------------------------

    try:
        await query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=keyboards.main_menu_keyboard(context)
        )
    except telegram.error.BadRequest as e:
        if "Message is not modified" in str(e):
            pass
        else:
            raise e


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any active conversation and preserves auth state."""
    # Preserve Auth Cache
    jwt = context.user_data.get('jwt')
    profile_data = context.user_data.get('profile_data')
    profile = context.user_data.get('profile')
    role = context.user_data.get('role')

    context.user_data.clear()

    if jwt:
        context.user_data['jwt'] = jwt
        context.user_data['profile_data'] = profile_data
        context.user_data['profile'] = profile
        context.user_data['role'] = role

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
            await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=keyboard)
    else:
        await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=keyboard)

    return ConversationHandler.END