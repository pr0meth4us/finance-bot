# --- Start of new file: telegram_bot/handlers/onboarding.py ---

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)

import api_client
import keyboards
from .common import start

# Conversation states
(
    ASK_LANGUAGE,
    ASK_USD_BALANCE,
    ASK_KHR_BALANCE
) = range(3)


async def onboarding_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Starts the mandatory onboarding flow for new users.
    This is typically triggered by the @authenticate_user decorator.
    """
    context.user_data.clear()
    # Re-cache the user profile, which contains the 'is_new_user' flag
    profile = context.application.user_data[update.effective_user.id].get(
        'user_profile'
    )
    context.user_data['user_profile'] = profile

    await update.message.reply_text(
        "Welcome to the finance bot! Let's get your account set up.\n\n"
        "First, what is your preferred language? (This setting is coming soon, "
        "please just type 'en' for English for now.)"
        # TODO: Add keyboard when languages are supported
        # reply_markup=keyboards.language_keyboard()
    )
    return ASK_LANGUAGE


async def received_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles language selection.
    For now, just accepts 'en' and moves to balance setup.
    """
    # In the future, this will set the user's language preference.
    # lang = update.message.text
    # api_client.update_user_setting(user_id, 'language', lang)

    await update.message.reply_text(
        "Great! Now, let's set your initial account balances.\n\n"
        "What is your current **USD** balance? (e.g., 100.50)"
    )
    return ASK_USD_BALANCE


async def received_usd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the initial USD balance."""
    try:
        amount = float(update.message.text)
        user_id = context.user_data['user_profile']['_id']

        # Call the new API endpoint to set the initial balance
        api_client.update_initial_balance(user_id, 'USD', amount)

        await update.message.reply_text(
            f"✅ Initial USD balance set to ${amount:,.2f}.\n\n"
            "Now, what is your current **KHR** balance? (e.g., 50000)"
        )
        return ASK_KHR_BALANCE

    except (ValueError, TypeError):
        await update.message.reply_text(
            "Invalid amount. Please enter a valid number (e.g., 100.50)."
        )
        return ASK_USD_BALANCE
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")
        return ConversationHandler.END


async def received_khr_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the initial KHR balance and ends onboarding."""
    try:
        amount = float(update.message.text)
        user_id = context.user_data['user_profile']['_id']

        api_client.update_initial_balance(user_id, 'KHR', amount)

        await update.message.reply_text(
            f"✅ Initial KHR balance set to {amount:,.0f} ៛."
        )

        # Onboarding is complete. Mark 'is_new_user' as false.
        context.user_data['user_profile']['is_new_user'] = False

        await update.message.reply_text(
            "🎉 **Setup Complete!**\n\n"
            "You're all set. I'll show you the main menu now."
        )
        # Manually call the start handler to display the main menu
        return await start(update, context)

    except (ValueError, TypeError):
        await update.message.reply_text(
            "Invalid amount. Please enter a valid number (e.g., 50000)."
        )
        return ASK_KHR_BALANCE
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")
        return ConversationHandler.END


onboarding_conversation_handler = ConversationHandler(
    entry_points=[
        # This handler is not started by a command,
        # but entered programmatically by the decorator
    ],
    states={
        ASK_LANGUAGE: [MessageHandler(
            filters.TEXT & ~filters.COMMAND, received_language
        )],
        ASK_USD_BALANCE: [MessageHandler(
            filters.TEXT & ~filters.COMMAND, received_usd_balance
        )],
        ASK_KHR_BALANCE: [MessageHandler(
            filters.TEXT & ~filters.COMMAND, received_khr_balance
        )],
    },
    fallbacks=[],
    per_message=False
)

# --- End of new file ---