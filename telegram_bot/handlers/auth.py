# telegram_bot/handlers/auth.py

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import api_client
import logging

log = logging.getLogger(__name__)


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Generates a login code for the user to enter on the website.
    """
    user = update.effective_user

    # 1. Request Code from Bifrost (via api_client)
    try:
        code = api_client.get_login_code(user.id)

        if code:
            msg = (
                f"🔐 <b>Web Login</b>\n\n"
                f"Your login code is: <code>{code}</code>\n\n"
                f"1. Go to https://savvify-web.vercel.app/\n"
                f"2. Select 'Telegram Code' (or just enter it if prompted).\n"
                f"3. Enter these 6 digits.\n\n"
                f"<i>Valid for 10 minutes.</i>"
            )
            await update.message.reply_text(msg, parse_mode='HTML')
        else:
            # api_client logs the specific error
            await update.message.reply_text(
                "❌ Service unavailable. Could not generate a login code. Please try again later.")

    except Exception as e:
        log.error(f"Login code generation failed: {e}")
        await update.message.reply_text("❌ An unexpected error occurred.")

    return ConversationHandler.END