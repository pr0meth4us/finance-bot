# --- telegram_bot/decorators.py (FULL) ---
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import api_client
from handlers.onboarding import onboarding_start
import logging

log = logging.getLogger(__name__)

def authenticate_user(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            log.warning("Decorator received update with no effective_user.")
            return ConversationHandler.END

        user_id = update.effective_user.id
        cached = context.user_data.get("user_profile")

        if not cached:
            log.info(f"User {user_id}: No profile in cache. Fetching from API.")
            profile = api_client.find_or_create_user(user_id)
            if not profile or profile.get("error"):
                msg = profile.get("error", "Auth failed.")
                log.error(f"User {user_id}: Auth failed or API error: {msg}")
                if update.message:
                    await update.message.reply_text(f"🚫 {msg}")
                elif update.callback_query:
                    await context.bot.answer_callback_query(
                        callback_query_id=update.callback_query.id,
                        text=f"🚫 {msg}",
                        show_alert=True,
                    )
                return ConversationHandler.END
            context.user_data["user_profile"] = profile
            log.info(f"User {user_id}: Profile fetched and cached.")
        else:
            log.info(f"User {user_id}: Profile found in cache.")

        # --- Onboarding redirect for first-time users ---
        is_complete = context.user_data["user_profile"].get("onboarding_complete")
        if not is_complete:
            log.info(f"User {user_id}: Onboarding_complete=False. Redirecting to onboarding.")

            # --- THIS IS THE FIX ---
            # This list must contain every function used inside the onboarding handler
            onboarding_functions = [
                "onboarding_start",
                "received_language",
                "received_currency_mode",
                "received_name_en",
                "received_name_km",
                "received_single_currency",
                "received_usd_balance",
                "received_khr_balance",
                "received_single_balance",
                "cancel_onboarding" # Don't forget the fallback
            ]
            # --- END FIX ---

            # Only start onboarding if we're not already inside it
            if func.__name__ not in onboarding_functions:
                log.info(f"User {user_id}: Handler '{func.__name__}' is not part of onboarding. Starting flow.")
                if update.message:
                    return await onboarding_start(update, context)
                if update.callback_query:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="Welcome! Let's start with some setup." # This is a fallback
                    )
                    return await onboarding_start(update.callback_query, context)
            else:
                log.info(f"User {user_id}: Already in onboarding handler '{func.__name__}'. Proceeding.")

        return await func(update, context, *args, **kwargs)

    return wrapped