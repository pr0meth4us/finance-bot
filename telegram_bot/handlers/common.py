# --- telegram_bot/handlers/common.py (Refactored) ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import telegram.error  # <-- NEW IMPORT
import keyboards
import api_client
from decorators import authenticate_user
from .helpers import format_summary_message
from utils.i18n import t


@authenticate_user
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays the main menu and forcibly ends any active conversation.
    NOTE: This handler is now largely redundant, as 'onboarding_start'
    handles this logic.
    It's kept for fallbacks in ConversationHandlers.
    """
    # --- REFACTOR: Get profile and JWT from context ---
    profile = context.user_data['profile']
    jwt = context.user_data['jwt']

    lang = profile.get('settings', {}).get('language', 'en')
    user_name = profile.get('name_en', 'User')
    if lang == 'km' and profile.get('name_km'):
        user_name = profile.get('name_km')

    text = t("common.welcome", context, name=user_name)
    keyboard = keyboards.main_menu_keyboard(context)
    chat_id = update.effective_chat.id

    # --- REFACTOR: Pass JWT ---
    summary_data = api_client.get_detailed_summary(jwt)
    summary_text = format_summary_message(summary_data, context)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                text + summary_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        # --- THIS IS THE FIX ---
        except telegram.error.BadRequest as e:
            if "Message is not modified" in str(e):
                pass  # Ignore if the message is the same
            else:
                raise e
        # --- END FIX ---
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

    # --- REFACTOR: Get JWT from context ---
    jwt = context.user_data['jwt']

    # --- REFACTOR: Pass JWT ---
    summary_data = api_client.get_detailed_summary(jwt)
    summary_text = format_summary_message(summary_data, context)
    text = t("common.quick_check_header", context) + summary_text

    # --- THIS IS THE FIX ---
    try:
        await query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=keyboards.main_menu_keyboard(context)
        )
    except telegram.error.BadRequest as e:
        if "Message is not modified" in str(e):
            pass  # Ignore if the user is just refreshing
        else:
            raise e
    # --- END FIX ---


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any active conversation."""

    # --- REFACTOR: Preserve auth cache on cancel ---
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
    # ---

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

    return ConversationHandler.END