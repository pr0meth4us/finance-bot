# telegram_bot/handlers/payment.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import time
import logging
import api_client
from decorators import authenticate_user

log = logging.getLogger(__name__)

@authenticate_user
async def upgrade_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the package selection menu."""
    user_id = update.effective_user.id
    log.debug(f"🐞 [Upgrade Start] User: {user_id}")

    # --- 1. UI FEEDBACK (Loading State) ---
    # We send this immediately because the DB/API sync below can take seconds.
    query = update.callback_query
    loading_msg = None

    if query:
        await query.answer()
        # If clicked from a menu, replace the menu with loading text
        loading_msg = await query.edit_message_text(
            "⏳ <b>Verifying subscription status...</b>\n"
            "<i>Syncing with Bifrost Identity...</i>",
            parse_mode='HTML'
        )
    else:
        # If typed /upgrade, reply with loading text
        loading_msg = await update.message.reply_text(
            "⏳ <b>Verifying subscription status...</b>\n"
            "<i>Syncing with Bifrost Identity...</i>",
            parse_mode='HTML'
        )

    # --- 2. DATA SYNC (The Slow Part) ---

    # Try to fetch profile from Finance DB (Source of Truth for "Premium")
    jwt = context.user_data.get('jwt')
    db_role = None

    if jwt:
        log.debug("🐞 [Upgrade Start] Fetching profile from Finance DB...")
        profile_data = api_client.get_my_profile(jwt)

        if profile_data and "role" in profile_data:
            db_role = profile_data["role"]
            log.debug(f"🐞 [Upgrade Start] DB says role is: {db_role}")
            # Update Context
            context.user_data["role"] = db_role
            if "profile" not in context.user_data:
                context.user_data["profile"] = {}
            context.user_data["profile"]["role"] = db_role
        else:
            log.error("🐞 [Upgrade Start] Failed to fetch profile (401 or Network).")
            # Edit the loading message to show error
            await loading_msg.edit_text(
                "⚠️ <b>Connection Error</b>\n\n"
                "We could not verify your subscription status with the Finance Server.\n"
                "Please try logging in again: /login",
                parse_mode='HTML'
            )
            return

    # --- 3. CHECK STATUS ---
    is_premium = False

    # Check DB role first
    if db_role:
        if isinstance(db_role, int) and db_role >= 2:
            is_premium = True
        elif isinstance(db_role, str) and db_role in ['premium_user', 'admin']:
            is_premium = True

    # Fallback to Bifrost Sync only if DB didn't say premium
    if not is_premium:
        log.debug("🐞 [Upgrade Start] DB says not premium. Checking Bifrost...")
        fresh_role = api_client.sync_subscription_status(user_id)
        if fresh_role == 'premium_user':
            is_premium = True
            # Update local to match Bifrost
            context.user_data["role"] = 'premium_user'

    if is_premium:
        log.debug("🐞 [Upgrade Start] User is premium. Showing success message.")
        await loading_msg.edit_text(
            "🌟 <b>You are already Premium!</b>\n\n"
            "You have full access to all features.\n"
            "There is no need to upgrade again.",
            parse_mode='HTML'
        )
        return

    # --- 4. SHOW MENU ---
    log.debug("🐞 [Upgrade Start] User is NOT premium. Showing packages.")
    keyboard = [
        [InlineKeyboardButton("📅 1 Month ($5.00)", callback_data="upgrade:1m")],
        [InlineKeyboardButton("🗓 1 Year ($45.00) - Save 25%", callback_data="upgrade:1y")]
    ]

    await loading_msg.edit_text(
        "<b>💎 Upgrade to Premium</b>\n\n"
        "Unlock advanced features like:\n"
        "• 📊 Advanced Analytics\n"
        "• 🏷 Custom Categories\n"
        "• 🤝 Unlimited Debt Tracking\n\n"
        "<b>Select a plan:</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


@authenticate_user
async def upgrade_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the package selection and generates the link."""
    query = update.callback_query
    await query.answer()

    # Parse choice (1m or 1y)
    duration_code = query.data.split(":")[1]
    log.debug(f"🐞 [Upgrade Confirm] User selected duration: {duration_code}")

    # Define Packages
    packages = {
        "1m": {"price": 5.00, "duration": "1m", "label": "1 Month"},
        "1y": {"price": 45.00, "duration": "1y", "label": "1 Year"}
    }

    plan = packages.get(duration_code)
    if not plan:
        log.error(f"🐞 [Upgrade Confirm] Invalid plan code: {duration_code}")
        await query.edit_message_text("❌ Invalid plan selected.")
        return

    # Generate Ref
    user_id = update.effective_user.id
    ref_id = f"finance_SUB_{user_id}_{int(time.time())}"
    log.debug(f"🐞 [Upgrade Confirm] Generated Ref: {ref_id}")

    # UI Feedback (Already acting as a loading state)
    await query.edit_message_text(f"🔄 Generating secure payment link for <b>{plan['label']}</b>...", parse_mode='HTML')

    # Call Bifrost API
    log.debug(f"🐞 [Upgrade Confirm] Calling create_payment_intent for ${plan['price']}...")
    intent = api_client.create_payment_intent(
        user_id=user_id,
        amount=plan['price'],
        duration=plan['duration'],
        target_role="premium_user",
        client_ref_id=ref_id
    )

    if not intent or not intent.get('success'):
        log.error(f"🐞 [Upgrade Confirm] Intent creation failed. Result: {intent}")
        await query.edit_message_text(
            "❌ Error: Could not contact payment gateway. Please try again later.",
            parse_mode='HTML'
        )
        return

    secure_link = intent['secure_link']
    manual_command = intent['manual_command']
    log.debug(f"🐞 [Upgrade Confirm] Success. Link: {secure_link}")

    keyboard = [
        [InlineKeyboardButton(f"💎 Pay ${plan['price']:.2f}", url=secure_link)]
    ]

    await query.edit_message_text(
        f"<b>💎 Confirm Upgrade: {plan['label']}</b>\n\n"
        f"Price: <b>${plan['price']:.2f}</b>\n\n"
        "1. Click the button below to pay via Bifrost.\n"
        "2. Send your receipt to the Bifrost Bot.\n"
        "3. Your features will unlock automatically!\n\n"
        f"<code>{manual_command}</code>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )