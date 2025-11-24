# telegram_bot/handlers/common.py

import telegram.error
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import keyboards
import api_client
from api_client import UpstreamUnavailable
from decorators import authenticate_user
from .helpers import format_summary_message
from utils.i18n import t

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")


@authenticate_user
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays the main menu (Dashboard).
    """
    profile = context.user_data.get('profile', {})
    jwt = context.user_data.get('jwt')

    lang = profile.get('settings', {}).get('language', 'en')
    user_name = profile.get('name_en', 'User')
    if lang == 'km' and profile.get('name_km'):
        user_name = profile.get('name_km')

    # --- DYNAMIC GREETING LOGIC ---
    now = datetime.now(PHNOM_PENH_TZ)
    hour = now.hour

    if 5 <= hour < 12:
        greeting_key = "common.greeting_morning"
    elif 12 <= hour < 17:
        greeting_key = "common.greeting_afternoon"
    elif 17 <= hour < 21:
        greeting_key = "common.greeting_evening"
    else:
        greeting_key = "common.greeting_night"
    # ------------------------------

    # --- GRACEFUL SUMMARY FETCH ---
    summary_text = ""
    try:
        # Pass JWT explicitly
        summary_data = api_client.get_detailed_summary(jwt)

        # Handle potential error dictionary return (non-exception 401 handling)
        if summary_data and "error" not in summary_data:
            summary_text = format_summary_message(summary_data, context)
        else:
            summary_text = t("common.summary_unavailable", context)

    except UpstreamUnavailable:
        summary_text = t("common.summary_unavailable", context)
    # ------------------------------

    greeting_text = t(greeting_key, context, name=user_name)

    if summary_text:
        final_text = f"{greeting_text}\n\n{summary_text}"
    else:
        final_text = greeting_text

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
    """Fetches and displays a quick summary."""
    query = update.callback_query
    jwt = context.user_data['jwt']

    try:
        summary_data = api_client.get_detailed_summary(jwt)

        if not summary_data or "error" in summary_data:
            await query.answer(t("common.upstream_alert", context), show_alert=True)
            return

        summary_text = format_summary_message(summary_data, context)

        header = t("common.quick_check_header", context)
        text = f"{header}\n{summary_text}"

        await query.answer("Fetching summary...")
        await query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=keyboards.main_menu_keyboard(context)
        )
    except UpstreamUnavailable:
        await query.answer(t("common.upstream_alert", context), show_alert=True)
    except telegram.error.BadRequest as e:
        if "Message is not modified" in str(e):
            await query.answer()
            pass
        else:
            raise e


@authenticate_user
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the user guide."""
    help_text = t("help.guide", context)
    await update.message.reply_text(help_text, parse_mode='HTML')


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any active conversation."""
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