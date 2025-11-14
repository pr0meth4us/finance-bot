# --- telegram_bot/decorators.py (Refactored) ---
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import api_client
import logging
from utils.i18n import t

log = logging.getLogger(__name__)


# --- NEW: Helper for sending auth error messages ---
async def _send_auth_error(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
    """Sends a standardized auth error message as a reply or callback alert."""
    if update.message:
        await update.message.reply_text(f"🚫 {message}")
    elif update.callback_query:
        await context.bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
            text=f"🚫 {message}",
            show_alert=True,
        )


def authenticate_user(func):
    """
    Refactored decorator for JWT authentication and profile fetching.

    1. Checks for a cached JWT. If missing, logs in via Bifrost.
    2. Checks for a cached Profile. If missing, fetches from /users/me.
    3. Checks for onboarding_complete flag.
    """

    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            log.warning("Decorator received update with no effective_user.")
            return ConversationHandler.END

        user_id = update.effective_user.id

        try:
            # --- 1. Get or Refresh JWT ---
            # TODO: Implement JWT expiration logic
            jwt = context.user_data.get("jwt")
            if not jwt:
                log.info(f"User {user_id}: No JWT in cache. Logging in via Bifrost.")
                login_data = api_client.bifrost_telegram_login(user_id)

                if "error" in login_data:
                    msg = login_data.get("error", "Auth API login failed.")
                    log.error(f"User {user_id}: Bifrost login failed: {msg}")
                    await _send_auth_error(update, context, msg)
                    return ConversationHandler.END

                jwt = login_data.get("jwt")
                context.user_data["jwt"] = jwt
                log.info(f"User {user_id}: JWT fetched and cached.")

            # --- 2. Get or Refresh Profile ---
            profile_data = context.user_data.get("profile_data")
            if not profile_data:
                log.info(f"User {user_id}: No profile in cache. Fetching from /users/me.")
                profile_data = api_client.get_my_profile(jwt)

                if "error" in profile_data:
                    msg = profile_data.get("error", "Failed to fetch user profile.")
                    log.error(f"User {user_id}: Profile fetch failed: {msg}")

                    # Clear the bad JWT so we re-login next time
                    context.user_data.pop("jwt", None)
                    await _send_auth_error(update, context, msg)
                    return ConversationHandler.END

                # Cache the full payload
                context.user_data["profile_data"] = profile_data
                # For convenience, cache the profile and role separately
                context.user_data["profile"] = profile_data.get("profile", {})
                context.user_data["role"] = profile_data.get("role", "user")
                log.info(f"User {user_id}: Profile fetched and cached. Role: {context.user_data['role']}")

            # --- 3. Check Onboarding Status ---
            # This logic remains from v1, but reads from the new cache
            is_complete = context.user_data.get("profile", {}).get("onboarding_complete")
            if not is_complete:
                log.info(f"User {user_id}: Onboarding_complete=False. Blocking handler '{func.__name__}'.")

                # Use i18n for the message
                message = t("common.onboarding_required", context)

                if update.message:
                    await update.message.reply_text(message)
                elif update.callback_query:
                    await context.bot.answer_callback_query(
                        callback_query_id=update.callback_query.id,
                        text=message,
                        show_alert=True,
                    )

                # Cleanly end the current conversation/handler
                return ConversationHandler.END

            # --- 4. Success ---
            return await func(update, context, *args, **kwargs)

        except Exception as e:
            log.error(f"Unhandled error in @authenticate_user for {user_id}: {e}", exc_info=True)
            await _send_auth_error(update, context, "An unexpected authentication error occurred.")
            return ConversationHandler.END

    return wrapped