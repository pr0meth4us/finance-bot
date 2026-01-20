from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import os

# You must set BIFROST_BOT_USERNAME in your .env (e.g., "MyBifrost_Bot")
BIFROST_BOT_USERNAME = os.getenv("BIFROST_BOT_USERNAME", "Bifrost_Bot")
# This is the finance bot's specific ID in Bifrost
MY_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID", "finance_bot")

async def upgrade_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Redirects user to the Central Bifrost Bot for payment.
    """
    # Create the deep link: t.me/BifrostBot?start=pay_finance_bot
    url = f"https://t.me/{BIFROST_BOT_USERNAME}?start=pay_{MY_CLIENT_ID}"

    keyboard = [
        [InlineKeyboardButton("💎 Pay with Bifrost ($5)", url=url)]
    ]

    await update.message.reply_text(
        "<b>Upgrade to Premium</b>\n\n"
        "We use <b>Bifrost</b> to securely handle payments.\n"
        "Click the button below to pay via ABA QR.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )