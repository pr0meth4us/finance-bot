# --- Start of refactored file: telegram_bot/decorators.py ---
import os
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import api_client # NEW IMPORT

def restricted(func):
    """
    A decorator that restricts access to a handler to only users
    with an 'active' subscription or an 'admin' role.
    """

    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Get the ID of the user who sent the message or pressed the button
        user_id = update.effective_user.id

        # 1. Check user status with the new backend endpoint
        user_status = api_client.find_or_create_user(user_id)

        error_message = None

        # Check for initial API errors (e.g., web service is down)
        if user_status is None or user_status.get('error'):
            error_text = user_status.get('error', 'The web service is unavailable. Please try again later.')
            print(f"🚫 API Error during auth check for user {user_id}: {error_text}")
            error_message = f"❌ System Error: {error_text}"

        # 2. Check if the user is a subscriber or admin
        elif user_status.get('subscription_status') != 'active' and not user_status.get('is_admin'):
            error_message = "🚫 **Access Denied:** Your subscription is inactive. Please renew to continue access."

        # 3. Check if user has completed the required onboarding flow (NEW REQUIREMENT)
        # This is a soft check, handled fully in the new /start handler.
        if user_status.get('subscription_status') == 'active' and not user_status.get('is_onboarded', False):
            # Pass the check but update the user_data to redirect to onboarding
            context.user_data['is_onboarded'] = False
        else:
            context.user_data['is_onboarded'] = True


        if error_message:
            # Send the denial message via the appropriate method
            if update.message:
                await update.message.reply_text(error_message, parse_mode='Markdown')
            elif update.callback_query:
                await context.bot.answer_callback_query(
                    callback_query_id=update.callback_query.id,
                    text=error_message,
                    show_alert=True
                )
            return

        # If the ID matches, is active, or is admin, run the original handler function
        return await func(update, context, *args, **kwargs)

    return wrapped

# --- End of refactored file: telegram_bot/decorators.py ---