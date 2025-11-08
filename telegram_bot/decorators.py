# --- Start of modified file: telegram_bot/decorators.py ---
import os
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import api_client
from handlers.onboarding import (
    onboarding_start, ASK_LANGUAGE
)


def authenticate_user(func):
    """
    A decorator that authenticates a user on every interaction.
    1. Gets the user's Telegram ID.
    2. Checks if the user's profile is cached in context.user_data.
    3. If not cached, fetches the user's profile from the API.
    4. Caches the user profile in context.user_data['user_profile'].
    5. Checks the user's 'subscription_status'.
    6. If active, runs the handler. If not, sends a denial message.
    7. NEW: If active AND 'is_new_user' is true, redirects to onboarding.
    """

    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE,
                      *args, **kwargs):
        if not update.effective_user:
            return

        user_id = update.effective_user.id
        user_profile = context.user_data.get('user_profile')

        if not user_profile:
            try:
                user_profile = api_client.find_or_create_user(user_id)

                if not user_profile:
                    raise Exception("API did not return a user profile.")

                if user_profile.get('error'):
                    error_message = user_profile['error']
                    if update.message:
                        await update.message.reply_text(
                            f"🚫 Access Denied: {error_message}"
                        )
                    elif update.callback_query:
                        await context.bot.answer_callback_query(
                            callback_query_id=update.callback_query.id,
                            text=f"🚫 Access Denied: {error_message}",
                            show_alert=True
                        )
                    return ConversationHandler.END

                context.user_data['user_profile'] = user_profile

            except Exception as e:
                print(f"🚫 Authentication FAILED for user {user_id}: {e}")
                if update.message:
                    await update.message.reply_text(
                        "🚫 Sorry, I couldn't verify your access at the "
                        "moment. Please try again later."
                    )
                elif update.callback_query:
                    await context.bot.answer_callback_query(
                        callback_query_id=update.callback_query.id,
                        text="🚫 Auth failed. Please try again.",
                        show_alert=True
                    )
                return ConversationHandler.END

        # --- Onboarding Check ---
        # Check if the user is new AND not already in an onboarding flow
        if user_profile.get('is_new_user'):
            # Determine if we are already in the onboarding conversation
            in_onboarding = False
            if 'active_conversation' in context.user_data:
                # This is a basic check. A real implementation might need
                # to check the conversation name or state.
                pass  # Assuming dev manages state correctly for now

            # If the function being called is NOT part of onboarding,
            # and they are a new user, force them into it.
            # We must allow 'cancel' to work.
            if func.__name__ not in [
                'onboarding_start', 'received_language',
                'received_usd_balance', 'received_khr_balance', 'cancel'
            ]:
                if update.message:
                    return await onboarding_start(update, context)
                if update.callback_query:
                    # Can't start a message-based flow from a button press
                    # easily. Send a message instead.
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="Welcome! Let's start with some setup."
                    )
                    return await onboarding_start(update.callback_query,
                                                  context)

        # Run the original handler function
        return await func(update, context, *args, **kwargs)

    return wrapped
# --- End of modified file ---