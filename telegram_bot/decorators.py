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
        # Answer query to stop loading animation, then send message
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

        user_id = update.effective_user.id

        try:
            # 1. Auth: Get or Refresh JWT
            jwt = context.user_data.get("jwt")
            if not jwt:
                log.info(f"User {user_id}: Logging in via Bifrost.")
                login_data = api_client.bifrost_telegram_login(user_id)

                if "error" in login_data:
                    msg = login_data.get("error", "Auth API login failed.")
                    log.error(f"User {user_id}: Bifrost login failed: {msg}")
                    await _send_auth_error(update, context, msg)
                    return ConversationHandler.END

                jwt = login_data.get("jwt")
                context.user_data["jwt"] = jwt

            # 2. Profile: Get or Refresh
            profile_data = context.user_data.get("profile_data")
            if not profile_data:
                profile_data = api_client.get_my_profile(jwt)

                if "error" in profile_data:
                    msg = profile_data.get("error", "Failed to fetch user profile.")
                    log.error(f"User {user_id}: Profile fetch failed: {msg}")

                    # Invalidate JWT to force re-login next time
                    context.user_data.pop("jwt", None)
                    await _send_auth_error(update, context, msg)
                    return ConversationHandler.END

                context.user_data["profile_data"] = profile_data
                context.user_data["profile"] = profile_data.get("profile", {})
                context.user_data["role"] = profile_data.get("role", "user")

            # 3. Onboarding Check
            is_complete = context.user_data.get("profile", {}).get("onboarding_complete")

            # Allow 'onboarding_start' to proceed even if not complete
            if not is_complete and func.__name__ != 'onboarding_start':
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

            # 4. Execute Handler
            return await func(update, context, *args, **kwargs)

        except UpstreamUnavailable:
            # Catches 500s/Timeouts from API calls inside auth OR inside the handler
            log.warning(f"User {user_id}: UpstreamUnavailable caught in decorator.")
            await _send_upstream_error(update, context)
            return ConversationHandler.END

        except Exception as e:
            log.error(f"Auth decorator error for {user_id}: {e}", exc_info=True)
            await _send_auth_error(update, context, "An unexpected error occurred.")
            return ConversationHandler.END

    return wrapped