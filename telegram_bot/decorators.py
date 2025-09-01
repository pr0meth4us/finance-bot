import os
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes


def restricted(func):
    """
    A decorator that restricts access to a handler to only the allowed user.
    """

    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Get the ID of the user who sent the message or pressed the button
        user_id = update.effective_user.id

        # Get the allowed user ID from our environment variables
        allowed_user_id = os.getenv("ALLOWED_USER_ID")

        if not allowed_user_id:
            print("⚠️ WARNING: ALLOWED_USER_ID is not set in the .env file.")
            return

        # Compare the user's ID with the allowed ID
        if str(user_id) != allowed_user_id:
            print(f"🚫 Unauthorized access denied for user {user_id}.")

            # Politely inform the unauthorized user
            if update.message:
                await update.message.reply_text("Sorry, this is a private bot. Access denied.")
            elif update.callback_query:
                await context.bot.answer_callback_query(
                    callback_query_id=update.callback_query.id,
                    text="Sorry, this is a private bot. Access denied.",
                    show_alert=True
                )
            return

        # If the ID matches, run the original handler function
        return await func(update, context, *args, **kwargs)

    return wrapped