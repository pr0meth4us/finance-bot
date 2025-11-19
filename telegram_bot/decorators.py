from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import api_client
import logging
from api_client import PremiumFeatureException, UpstreamUnavailable

log = logging.getLogger(__name__)


def authenticate_user(func):
    """
    Decorator to ensure the user is authenticated with Bifrost
    and has a valid profile cached in context.user_data.
    """

    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            log.warning("Decorator received update with no effective_user.")
            return ConversationHandler.END

        user = update.effective_user
        user_id = user.id

        # 1. Check local cache (Context)
        # We store the full profile in user_data['profile'] and the JWT in user_data['jwt']
        cached_profile = context.user_data.get("profile")
        cached_jwt = context.user_data.get("jwt")

        if not cached_profile or not cached_jwt:
            log.info(f"User {user_id}: No valid session. Initiating Bifrost Login...")

            # A. Perform Bifrost Handshake (Signs data -> Bifrost -> Returns JWT)
            jwt = api_client.login_to_bifrost(user)

            if not jwt:
                msg = "⚠️ **Authentication Failed**\nCould not verify your identity with the secure server."
                if update.message:
                    await update.message.reply_text(msg, parse_mode='Markdown')
                elif update.callback_query:
                    await context.bot.answer_callback_query(update.callback_query.id, text=msg, show_alert=True)
                return ConversationHandler.END

            # B. Fetch Profile from Web Service using the new JWT
            try:
                # This returns { "profile": {...}, "role": "..." }
                resp = api_client.get_my_profile(user_id=user_id)

                context.user_data["jwt"] = jwt
                context.user_data["profile"] = resp["profile"]
                context.user_data["role"] = resp.get("role", "user")

                log.info(f"User {user_id}: Auth successful. Role: {resp.get('role')}")

            except PremiumFeatureException:
                # This shouldn't technically happen on /me, but handling safely
                if update.message:
                    await update.message.reply_text("🚫 Access Denied: Subscription issue.")
                return ConversationHandler.END
            except UpstreamUnavailable:
                msg = "⚠️ System Unavailable. Please try again later."
                if update.message:
                    await update.message.reply_text(msg)
                elif update.callback_query:
                    await context.bot.answer_callback_query(update.callback_query.id, text=msg, show_alert=True)
                return ConversationHandler.END
            except Exception as e:
                log.error(f"Profile fetch error: {e}")
                if update.message:
                    await update.message.reply_text("⚠️ Connection Error.")
                return ConversationHandler.END

        # 2. Onboarding Check
        # We allow /start and specific onboarding callbacks to proceed even if incomplete
        profile = context.user_data["profile"]
        is_complete = profile.get("onboarding_complete", False)

        command_text = update.message.text if update.message and update.message.text else ""
        is_start_cmd = command_text.startswith("/start")
        is_reset_cmd = command_text.startswith("/reset")

        # Callbacks related to onboarding
        is_onboarding_cb = False
        if update.callback_query and update.callback_query.data:
            cb = update.callback_query.data
            if cb.startswith("start") or cb.startswith("reset_") or cb.startswith("change_lang") or cb.startswith(
                    "set_balance") or cb.startswith("confirm_switch"):
                is_onboarding_cb = True

        # Block if not onboarded and not trying to onboard
        if not is_complete and not (is_start_cmd or is_reset_cmd or is_onboarding_cb):
            # Special case: Allow the function 'onboarding_start' or similar if explicitly wrapped
            # But usually checking the command is enough.

            log.info(f"User {user_id}: Onboarding incomplete. Blocking access.")
            msg = "⚠️ **Setup Required**\n\nPlease complete your account setup first.\nType /start to begin."

            if update.message:
                await update.message.reply_text(msg, parse_mode='Markdown')
            elif update.callback_query:
                await context.bot.answer_callback_query(
                    callback_query_id=update.callback_query.id,
                    text="Please complete setup first. Type /start.",
                    show_alert=True
                )
            return ConversationHandler.END

        return await func(update, context, *args, **kwargs)

    return wrapped