# telegram_bot/decorators.py

from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import api_client
from api_client import UpstreamUnavailable
import logging
from utils.i18n import t

log = logging.getLogger(__name__)


async def _send_auth_error(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
    """Sends a standardized auth error message."""
    if update.message:
        await update.message.reply_text(f"🚫 {message}")
    elif update.callback_query:
        await context.bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
            text=f"🚫 {message}",
            show_alert=True,
        )


async def _send_upstream_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a friendly 'Service Unavailable' message."""
    msg = t("common.upstream_error", context)

    if update.callback_query:
        await context.bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
            text=t("common.upstream_alert", context),
            show_alert=True
        )
    elif update.message:
        await update.message.reply_text(msg, parse_mode='Markdown')


def authenticate_user(func):
    """
    Decorator for JWT authentication and profile fetching.
    """

    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return ConversationHandler.END

        user = update.effective_user
        user_id = user.id

        try:
            # 1. Auth: Get or Refresh JWT
            jwt = context.user_data.get("jwt")

            if not jwt:
                log.info(f"User {user_id}: Logging in via Bifrost.")
                # New api_client returns the JWT string directly or None
                jwt = api_client.login_to_bifrost(user)

                if not jwt:
                    msg = "Authentication failed."
                    log.error(f"User {user_id}: Bifrost login returned None.")
                    await _send_auth_error(update, context, msg)
                    return ConversationHandler.END

            # Lazy Provisioning is now handled by the backend upon the first API call.
            # We skip explicit sync-session here.
            context.user_data["jwt"] = jwt

            # 2. Profile: Get or Refresh
            profile_data = context.user_data.get("profile_data")
            if not profile_data:
                # Pass JWT explicitly
                # This call triggers lazy provisioning on the backend if user is missing
                profile_data = api_client.get_my_profile(jwt)

                # Handle Auth Errors (401 from Web Service)
                if profile_data and profile_data.get("status") == 401:
                    log.warning(f"User {user_id}: JWT expired. Clearing session.")
                    context.user_data.pop("jwt", None)
                    # Optional: Retry once? For now, ask user to retry
                    await _send_auth_error(update, context, "Session expired. Please try again.")
                    return ConversationHandler.END

                if not profile_data or "error" in profile_data:
                    msg = profile_data.get("error", "Failed to fetch profile.") if profile_data else "Connection error."
                    log.error(f"User {user_id}: Profile fetch failed: {msg}")
                    context.user_data.pop("jwt", None)  # Clear invalid token
                    await _send_auth_error(update, context, msg)
                    return ConversationHandler.END

                context.user_data["profile_data"] = profile_data
                context.user_data["profile"] = profile_data.get("profile", {})
                context.user_data["role"] = profile_data.get("role", "user")

            # 3. Onboarding Check
            is_complete = context.user_data.get("profile", {}).get("onboarding_complete")

            if not is_complete and func.__name__ != 'onboarding_start':
                # Check if user is trying to run start/reset
                msg_text = update.message.text if update.message else ""
                if msg_text and (msg_text.startswith("/start") or msg_text.startswith("/reset")):
                    return await func(update, context, *args, **kwargs)

                log.info(f"User {user_id}: Onboarding incomplete. Blocking {func.__name__}.")
                message = t("common.onboarding_required", context)

                if update.message:
                    await update.message.reply_text(message)
                elif update.callback_query:
                    await context.bot.answer_callback_query(
                        callback_query_id=update.callback_query.id,
                        text=message,
                        show_alert=True,
                    )
                return ConversationHandler.END

            return await func(update, context, *args, **kwargs)

        except UpstreamUnavailable:
            log.warning(f"User {user_id}: UpstreamUnavailable caught in decorator.")
            await _send_upstream_error(update, context)
            return ConversationHandler.END

        except Exception as e:
            log.error(f"Auth decorator error for {user_id}: {e}", exc_info=True)
            await _send_auth_error(update, context, "An unexpected error occurred.")
            return ConversationHandler.END

    return wrapped