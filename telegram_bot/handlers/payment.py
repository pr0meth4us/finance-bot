from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import os

BIFROST_BOT_USERNAME = os.getenv("BIFROST_BOT_USERNAME")
MY_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID")

async def upgrade_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = "5.00"
    # Construct the start payload
    payload = f"pay_{MY_CLIENT_ID}_{price}"

    # 1. Deep Link Button
    url = f"https://t.me/{BIFROST_BOT_USERNAME}?start={payload}"

    # 2. Manual Command (for Copy-Paste)
    manual_command = f"/start {payload}"

    keyboard = [
        [InlineKeyboardButton(f"💎 Pay with Bifrost (${price})", url=url)]
    ]

    await update.message.reply_text(
        f"<b>💎 Upgrade to Premium</b>\n\n"
        f"Unlock advanced features for <b>${price}/mo</b>.\n\n"
        "Copy the command below and send it to @{BIFROST_BOT_USERNAME}:\n\n"
        f"<code>{manual_command}</code>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )