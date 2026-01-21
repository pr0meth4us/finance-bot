from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import os
from decorators import authenticate_user

BIFROST_BOT_USERNAME = os.getenv("BIFROST_BOT_USERNAME")
MY_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID")

@authenticate_user
async def upgrade_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Check if already premium
    role = context.user_data.get('role', 'user')

    if role == 'premium_user':
        await update.message.reply_text(
            "🌟 <b>You are already Premium!</b>\n\n"
            "You have full access to all features.\n"
            "There is no need to upgrade again.",
            parse_mode='HTML'
        )
        return

    # 2. If not premium, show payment options
    price = "5.00"
    duration = "1m"
    target_role = "premium_user"
    user_ref = update.effective_user.id

    # Bifrost 1.4.0+ Format: pay_CLIENTID__PRICE__DURATION__ROLE__REF
    payload = f"pay_{MY_CLIENT_ID}__{price}__{duration}__{target_role}__{user_ref}"

    url = f"https://t.me/{BIFROST_BOT_USERNAME}?start={payload}"
    manual_command = f"/start {payload}"

    keyboard = [
        [InlineKeyboardButton(f"💎 Pay with Bifrost (${price}/mo)", url=url)]
    ]

    await update.message.reply_text(
        f"<b>💎 Upgrade to Premium</b>\n\n"
        f"Unlock advanced features for <b>${price}/mo</b>.\n\n"
        "1. Click the button below to pay via Bifrost.\n"
        "2. Send your receipt to the Bifrost Bot.\n"
        "3. Your features will unlock automatically!\n\n"
        f"<code>{manual_command}</code>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )