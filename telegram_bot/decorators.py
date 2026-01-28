# telegram_bot/decorators.py

import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest

import api_client
from api_client.core import PremiumFeatureException, UpstreamUnavailable
from utils.i18n import t

log = logging.getLogger(__name__)


async def _send_auth_error(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str, show_alert=False):
    """
    Helper to safely display errors to the user via CallbackQuery or Message.
    """
    if update.callback_query:
        try:
            if show_alert:
                await update.callback_query.answer(message, show_alert=True)
            else:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(message)
        except BadRequest as e:
            # If the message content is identical, Telegram raises MessageNotModified.
            # We can safely ignore this as the UI is already in the desired state.
            if "Message is not modified" in str(e):
                log.warning("Supressed MessageNotModified error in auth error handler.")
            else:
                # If we can't edit (e.g. message too old), try sending a fresh message
                try:
                    await context.bot.send_message(update.effective_chat.id, message)
                except Exception as inner_e:
                    log.error(f"Failed to send fallback auth error: {inner_e}")
    else:
        await update.message.reply_text(message)


def authenticate_user(func):
    """
    Decorator: Ensures the user is logged in.
    Also handles global API exceptions like Premium limits.
    """

    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user

        # 1. Check Local Cache
        jwt = api_client.get_cached_token(user.id)

        # 2. Login if missing
        if not jwt:
            log.info(f"User {user.id}: Logging in via Bifrost.")
            jwt = api_client.login_to_bifrost(user)
            if not jwt:
                # Login Failed
                from keyboards import login_keyboard
                msg = t("auth.login_required", context)
                if update.callback_query:
                    await update.callback_query.message.reply_text(msg, reply_markup=login_keyboard(context))
                else:
                    await update.message.reply_text(msg, reply_markup=login_keyboard(context))
                return ConversationHandler.END

        # 3. Store Token in Context
        context.user_data['jwt'] = jwt
        context.user_data['telegram_id'] = user.id

        # 4. Ensure Profile & Role are Loaded (FIX)
        # If the bot restarted, we might have the JWT (from cache/login) but not the profile data.
        if 'profile' not in context.user_data or not context.user_data.get('profile'):
            try:
                # log.info(f"User {user.id}: Fetching missing profile data.")
                user_settings = api_client.get_user_settings(jwt)

                if user_settings and 'profile' in user_settings:
                    profile = user_settings['profile']
                    context.user_data['profile'] = profile
                    context.user_data['role'] = profile.get('role', 'user')
                    # log.info(f"User {user.id}: Profile loaded. Role: {context.user_data['role']}")
                else:
                    # Fallback if settings fetch fails (e.g. backend error)
                    # We don't block the user, but they will be 'User' and 'user' role.
                    log.warning(f"User {user.id}: Failed to fetch profile. Using defaults.")
                    context.user_data['profile'] = {}
                    context.user_data['role'] = 'user'
            except Exception as e:
                log.error(f"Error fetching profile in decorator: {e}")
                context.user_data['profile'] = {}

        # 5. Execute Handler with Global Error Catching
        try:
            return await func(update, context, *args, **kwargs)

        except PremiumFeatureException:
            # Handle Premium Limits Gracefully
            upsell_msg = t("common.premium_required", context)
            await _send_auth_error(update, context, upsell_msg, show_alert=True)
            return ConversationHandler.END

        except UpstreamUnavailable:
            # Handle Server Errors
            error_msg = t("common.upstream_error", context)
            await _send_auth_error(update, context, error_msg, show_alert=False)
            return ConversationHandler.END

        except BadRequest as e:
            # Swallow "Message not modified" errors to prevent crashes on double-clicks
            if "Message is not modified" in str(e):
                log.info(f"Ignored MessageNotModified in {func.__name__}")
                try:
                    await update.callback_query.answer()
                except:
                    pass
                return
            log.error(f"Telegram BadRequest in {func.__name__}: {e}")
            raise e

        except Exception as e:
            log.error(f"Unhandled error in {func.__name__}: {e}", exc_info=True)
            await _send_auth_error(update, context, t("common.error_generic", context))
            return ConversationHandler.END

    return wrapped