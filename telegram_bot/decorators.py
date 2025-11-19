from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import api_client
import logging

log = logging.getLogger(__name__)


def authenticate_user(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            log.warning("Decorator received update with no effective_user.")
            return ConversationHandler.END

        user = update.effective_user
        user_id = user.id

        # 1. Check if we have a JWT (api_client manages the cache)
        # We attempt a 'soft' check by trying to login if the token is missing.
        # Note: We don't access _USER_TOKENS directly; we rely on login_to_bifrost to handle it.

        # 2. Ensure we are logged in to Bifrost
        # We verify by checking if we have a profile cached in context.user_data.
        # If context is empty, we must fully authenticate (login -> get JWT -> fetch profile)

        cached_profile = context.user_data.get("user_profile")

        if not cached_profile:
            log.info(f"User {user_id}: No profile in cache. Starting authentication sequence.")

            # A. Perform Bifrost Login (Headless Widget Flow)
            jwt = api_client.login_to_bifrost(user)

            if not jwt:
                msg = "⚠️ Authentication failed. Could not verify identity with Bifrost."
                if update.message:
                    await update.message.reply_text(msg)
                elif update.callback_query:
                    await context.bot.answer_callback_query(update.callback_query.id, text=msg, show_alert=True)
                return ConversationHandler.END

            # B. Fetch Profile from Web Service using the new JWT
            # The JWT is now internally cached by api_client for subsequent calls
            profile_response = api_client.get_my_profile(user_id)

            if not profile_response:
                msg = "⚠️ Connection error. Could not fetch user profile."
                if update.message:
                    await update.message.reply_text(msg)
                elif update.callback_query:
                    await context.bot.answer_callback_query(update.callback_query.id, text=msg, show_alert=True)
                return ConversationHandler.END

            if profile_response.get("error"):
                # Handle Access Denied (e.g., Subscription Inactive)
                error_msg = profile_response["error"]
                if update.message:
                    await update.message.reply_text(f"🚫 Access Denied: {error_msg}")
                elif update.callback_query:
                    await context.bot.answer_callback_query(
                        callback_query_id=update.callback_query.id,
                        text=f"🚫 Access Denied: {error_msg}",
                        show_alert=True
                    )
                return ConversationHandler.END

            # C. Cache the profile
            # The endpoint returns { "profile": {...}, "role": ... }
            context.user_data["user_profile"] = profile_response["profile"]
            context.user_data["user_role"] = profile_response.get("role")
            log.info(f"User {user_id}: Authentication successful. Profile cached.")

        else:
            pass
            # log.info(f"User {user_id}: Profile found in cache.")

        # 3. Onboarding Check
        is_complete = context.user_data["user_profile"].get("onboarding_complete")

        # Allow users to re-run /start even if not onboarded, so they can restart the flow
        # But block other commands
        if not is_complete:
            command = update.message.text if update.message and update.message.text else ""
            is_start = command.startswith("/start") or (update.callback_query and update.callback_query.data == "start")

            # If not running /start and not onboarded, block
            if func.__name__ != 'onboarding_start' and not is_start:
                log.info(f"User {user_id}: Onboarding incomplete. Blocking handler '{func.__name__}'.")
                if update.message:
                    await update.message.reply_text("Please complete the setup first. Type /start to begin.")
                elif update.callback_query:
                    await context.bot.answer_callback_query(
                        callback_query_id=update.callback_query.id,
                        text="Please complete the setup first. Type /start to begin.",
                        show_alert=True,
                    )
                return ConversationHandler.END

        return await func(update, context, *args, **kwargs)

    return wrapped