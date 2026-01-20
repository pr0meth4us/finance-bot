from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import os

BIFROST_BOT_USERNAME = os.getenv("BIFROST_BOT_USERNAME", "Bifrost_Bot")
MY_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID", "finance_bot")

async def upgrade_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Redirects user to the Central Bifrost Bot for payment.
    Link format: t.me/Bot?start=pay_CLIENTID_PRICE
    """
    price = "5.00"
    url = f"https://t.me/{BIFROST_BOT_USERNAME}?start=pay_{MY_CLIENT_ID}_{price}"

    keyboard = [
        [InlineKeyboardButton(f"💎 Pay with Bifrost (${price})", url=url)]
    ]

    await update.message.reply_text(
        f"<b>Upgrade to Premium</b>\n\n"
        f"Unlock advanced features for <b>${price}/mo</b>.\n"
        "Click the button below to pay securely.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )