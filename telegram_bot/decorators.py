# --- Start of modified file: telegram_bot/decorators.py ---
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import api_client
# from handlers.onboarding import onboarding_start # --- REMOVED
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

        # --- MODIFIED ONBOARDING REDIRECT ---
        is_complete = context.user_data["user_profile"].get("onboarding_complete")
        if not is_complete:
            # Don't redirect. Just block the handler and tell the user what to do.
            # This prevents the decorator from returning a state to the wrong handler.
            log.info(f"User {user_id}: Onboarding_complete=False. Blocking handler '{func.__name__}'.")

            if update.message:
                await update.message.reply_text("Please complete the setup first. Type /start to begin.")
            elif update.callback_query:
                await context.bot.answer_callback_query(
                    callback_query_id=update.callback_query.id,
                    text="Please complete the setup first. Type /start to begin.",
                    show_alert=True,
                )

            # Cleanly end the current conversation/handler
            return ConversationHandler.END
        # --- END MODIFICATION ---

        return await func(update, context, *args, **kwargs)

    return wrapped
# --- End of modified file ---