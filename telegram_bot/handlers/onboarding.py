# --- Start of modified file: telegram_bot/handlers/onboarding.py ---

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

import api_client
import keyboards
# from .common import start  <-- REMOVED TO FIX CIRCULAR IMPORT
from utils.i18n import t

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
    # --- THIS IS THE FIX ---
    # The decorator already put the profile in context.user_data
    # We must preserve it.
    user_profile = context.user_data.get('user_profile')
    context.user_data.clear()
    context.user_data['user_profile'] = user_profile
    # --- END FIX ---

    # --- MODIFICATION: ---
    # 1. Ask for language (using "en" as the default for this first question)
    # 2. Use the new language_keyboard()
    # 3. Return ASK_LANGUAGE to wait for button press
    # 4. Removed the "double throw" of asking for USD balance here
    await (update.message or update.callback_query.message).reply_text(
        t("onboarding.welcome", context),
        reply_markup=keyboards.language_keyboard()
    )
    return ASK_LANGUAGE


async def received_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles language selection from the callback buttons.
    """
    query = update.callback_query
    await query.answer()

    lang = query.data.split(':')[-1]
    user_id = context.user_data['user_profile']['_id']

    # Save to DB
    api_client.update_language(user_id, lang)

    # Save to local cache so the *next* message is translated
    context.user_data['user_profile']['settings']['language'] = lang

    # --- MODIFICATION: ---
    # Now that language is set, ask for USD balance.
    # The t() function will now use the language (lang) we just set.
    await query.edit_message_text(
        t("onboarding.ask_usd_balance", context)
    )
    return ASK_USD_BALANCE


async def received_usd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the initial USD balance."""
    try:
        amount = float(update.message.text)
        user_id = context.user_data['user_profile']['_id']

        api_client.update_initial_balance(user_id, 'USD', amount)

        # This message will be in the user's chosen language
        await update.message.reply_text(
            t("onboarding.usd_balance_set", context, amount=amount)
        )
        return ASK_KHR_BALANCE

    except (ValueError, TypeError):
        await update.message.reply_text(
            t("onboarding.invalid_amount_usd", context)
        )
        return ASK_USD_BALANCE
    except Exception as e:
        await update.message.reply_text(t("common.error_generic", context, error=e))
        return ConversationHandler.END


async def received_khr_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the initial KHR balance and ends onboarding."""
    try:
        from .common import start  # <-- LOCAL IMPORT TO FIX CIRCULAR DEPENDENCY

        amount = float(update.message.text)
        user_id = context.user_data['user_profile']['_id']

        api_client.update_initial_balance(user_id, 'KHR', amount)

        await update.message.reply_text(
            t("onboarding.khr_balance_set", context, amount=amount)
        )

        # --- THIS IS THE FIX ---
        # Mark onboarding as complete in the DB and local cache
        api_client.complete_onboarding(user_id)
        context.user_data['user_profile']['onboarding_complete'] = True
        # --- END FIX ---

        await update.message.reply_text(
            t("onboarding.setup_complete", context)
        )
        return await start(update, context)

    except (ValueError, TypeError):
        await update.message.reply_text(
            t("onboarding.invalid_amount_khr", context)
        )
        return ASK_KHR_BALANCE
    except Exception as e:
        await update.message.reply_text(t("common.error_generic", context, error=e))
        return ConversationHandler.END


onboarding_conversation_handler = ConversationHandler(
    entry_points=[
        # This handler is entered programmatically by the decorator
    ],
    states={
        # --- MODIFICATION: Changed from MessageHandler to CallbackQueryHandler ---
        ASK_LANGUAGE: [
            CallbackQueryHandler(received_language, pattern='^lang:')
        ],
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

# --- End of modified file ---