# --- telegram_bot/decorators.py (FULL) ---
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import api_client
from handlers.onboarding import onboarding_start

def authenticate_user(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return ConversationHandler.END

        user_id = update.effective_user.id
        cached = context.user_data.get("user_profile")

        if not cached:
            profile = api_client.find_or_create_user(user_id)
            if not profile or profile.get("error"):
                msg = profile.get("error", "Auth failed.")
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

        # Onboarding redirect for first-time users
        if context.user_data["user_profile"].get("is_new_user"):
            # Only start onboarding if we're not already inside it
            if func.__name__ not in [
                "onboarding_start", "received_language",
                "received_usd_balance", "received_khr_balance", "cancel"
            ]:
                if update.message:
                    return await onboarding_start(update, context)
                if update.callback_query:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="Welcome! Let's start with some setup."
                    )
                    return await onboarding_start(update.callback_query, context)

        return await func(update, context, *args, **kwargs)

    return wrapped
