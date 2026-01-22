from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler
import api_client
from decorators import authenticate_user
from utils.i18n import t

async def show_premium_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays Premium options or status.
    Prevents generating a payment link if already premium.
    """
    query = update.callback_query
    await query.answer()

    jwt = context.user_data.get('jwt')
    if not jwt:
        await query.edit_message_text("⚠️ Authentication lost. Please type /start.")
        return

    # 1. Check Status
    user_settings = api_client.get_user_settings(jwt)
    if not user_settings or "error" in user_settings:
        await query.edit_message_text("⚠️ Could not fetch profile. Try again later.")
        return

    role = user_settings.get('profile', {}).get('role', 'user')
    # Update local context just in case
    context.user_data['role'] = role

    # 2. Block Double Payment
    if role == 'premium_user':
        await query.edit_message_text(
            "🌟 **You are already Premium!**\n\n"
            "Your subscription is active. You have full access to:\n"
            "✅ Custom Categories\n"
            "✅ Unlimited Accounts\n"
            "✅ Advanced Reports",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]])
        )
        return

    # 3. Generate Payment Link (Secure Intent) for Non-Premium
    await query.edit_message_text("🔄 Generating secure payment link...", parse_mode='Markdown')

    # Call your API client which wraps Bifrost's secure-intent
    # This assumes api_client has a method for this, or we construct the payload here
    try:
        # Example price: $2.99 USD
        intent = api_client.create_payment_intent(jwt, amount=2.99, currency='USD')

        if intent and intent.get('success'):
            pay_url = intent.get('secure_link')
            keyboard = [
                [InlineKeyboardButton("💎 Subscribe ($2.99)", url=pay_url)],
                [InlineKeyboardButton("🔙 Cancel", callback_data="menu")]
            ]
            await query.edit_message_text(
                "💎 **Upgrade to Premium**\n\n"
                "Unlock the full power of Savvify:\n"
                "- Custom Categories\n"
                "- CSV Exports\n"
                "- Priority Support",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            error = intent.get('error', 'Unknown error')
            await query.edit_message_text(f"❌ Could not generate payment link: {error}")

    except Exception as e:
        await query.edit_message_text("❌ Error connecting to payment gateway.")