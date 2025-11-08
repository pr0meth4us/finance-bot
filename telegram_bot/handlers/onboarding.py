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
from .common import start
from ..utils.i18n import t

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
    profile = context.application.user_data[update.effective_user.id].get(
        'user_profile'
    )
    context.user_data['user_profile'] = profile

    # Since this is the first interaction, we don't know the language.
    # We will ask in English, then update.
    # A more advanced flow might show a language picker first.
    await (update.message or update.callback_query.message).reply_text(
        t("onboarding.welcome", context)
        # For now, we skip language selection and default to 'en'
        # reply_markup=keyboards.language_keyboard()
    )

    # Skipping language selection for now
    await (update.message or update.callback_query.message).reply_text(
        t("onboarding.ask_usd_balance", context)
    )
    return ASK_USD_BALANCE
    # return ASK_LANGUAGE # Enable this when language selection is active


async def received_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles language selection.
    """
    # query = update.callback_query
    # await query.answer()
    # lang = query.data.split(':')[-1]

    # For now, just using text
    lang = update.message.text
    if lang not in ['en', 'km']:
        await update.message.reply_text(
            t("onboarding.ask_language_fallback", context)
        )
        return ASK_LANGUAGE

    # user_id = context.user_data['user_profile']['_id']
    # api_client.update_user_setting(user_id, 'language', lang)
    context.user_data['user_profile']['settings']['language'] = lang

    await update.message.reply_text(
        t("onboarding.language_selected", context, lang=lang)
    )
    return ASK_USD_BALANCE


async def received_usd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the initial USD balance."""
    try:
        amount = float(update.message.text)
        user_id = context.user_data['user_profile']['_id']

        api_client.update_initial_balance(user_id, 'USD', amount)

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
        amount = float(update.message.text)
        user_id = context.user_data['user_profile']['_id']

        api_client.update_initial_balance(user_id, 'KHR', amount)

        await update.message.reply_text(
            t("onboarding.khr_balance_set", context, amount=amount)
        )

        context.user_data['user_profile']['is_new_user'] = False

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
        # ASK_LANGUAGE: [
        #     CallbackQueryHandler(received_language, pattern='^lang:')
        # ],
        # Temp: Use text for language
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

# --- End of modified file ---