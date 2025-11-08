# --- Start of modified file: telegram_bot/decorators.py ---
import os
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import api_client # We need the api_client for the new decorator

def authenticate_user(func):
    """
    A decorator that authenticates a user on every interaction.
    1. Gets the user's Telegram ID.
    2. Checks if the user's profile is cached in context.user_data.
    3. If not cached, fetches the user's profile from the API (/api/auth/find_or_create).
    4. Caches the user profile in context.user_data['user_profile'].
    5. Checks the user's 'subscription_status'.
    6. If active, runs the handler. If not, sends a denial message and stops.
    """

    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Always get the user ID
        if not update.effective_user:
            # This can happen in some edge cases (e.g., channel posts)
            return

        user_id = update.effective_user.id

        # Check for cached profile
        user_profile = context.user_data.get('user_profile')

        if not user_profile:
            # Not cached, or first interaction. Fetch from API.
            try:
                user_profile = api_client.find_or_create_user(user_id)

                if not user_profile:
                    # API returned None or error
                    raise Exception("API did not return a user profile.")

                if user_profile.get('error'):
                    # API returned a specific error, e.g., "Subscription not active"
                    error_message = user_profile['error']
                    if update.message:
                        await update.message.reply_text(f"🚫 Access Denied: {error_message}")
                    elif update.callback_query:
                        await context.bot.answer_callback_query(
                            callback_query_id=update.callback_query.id,
                            text=f"🚫 Access Denied: {error_message}",
                            show_alert=True
                        )
                    return ConversationHandler.END # Stop conversation

                # Store successful profile in cache
                context.user_data['user_profile'] = user_profile

            except Exception as e:
                print(f"🚫 Authentication FAILED for user {user_id}: {e}")
                # Handle generic API or network failure
                if update.message:
                    await update.message.reply_text("🚫 Sorry, I couldn't verify your access at the moment. Please try again later.")
                elif update.callback_query:
                    await context.bot.answer_callback_query(
                        callback_query_id=update.callback_query.id,
                        text="🚫 Auth failed. Please try again.",
                        show_alert=True
                    )
                return ConversationHandler.END # Stop conversation

        # --- At this point, the user is authenticated and their profile is cached ---

        # Handle "is_new_user" flag from API for onboarding
        if user_profile.get('is_new_user'):
            # This is a new user, we must force them into the onboarding flow.
            # We'll add this logic in Part 2. For now, we'll just remove the flag.
            context.user_data['user_profile']['is_new_user'] = False # Mark as 'not new'

        # Run the original handler function (e.g., start, quick_check)
        return await func(update, context, *args, **kwargs)

    return wrapped
# --- End of modified file ---