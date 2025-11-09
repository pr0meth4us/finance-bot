# --- Start of modified file: telegram_bot/handlers/onboarding.py ---

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
import logging
import api_client
from utils.i18n import t

log = logging.getLogger(__name__)

# Conversation states
# --- THIS IS THE FIX ---
# Offset states by 100 to prevent collision with other handlers' states (which start at 0).
# The decorator on other handlers returns ASK_LANGUAGE (now 100),
# which other handlers (like unified_message_conversation_handler) will not
# confuse with their own state 0 (SELECT_CATEGORY).
(
    ASK_LANGUAGE,
    ASK_CURRENCY_MODE,
    ASK_NAME_EN,
    ASK_NAME_KM,
    ASK_SINGLE_CURRENCY,
    ASK_USD_BALANCE,
    ASK_KHR_BALANCE,
    ASK_SINGLE_BALANCE
) = range(100, 108)
# --- END FIX ---


async def onboarding_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Starts the mandatory onboarding flow for new users.
    This is triggered by the @authenticate_user decorator.
    """
    user_id = update.effective_user.id
    log.info(f"User {user_id}: Entering onboarding_start.")

    user_profile = context.user_data.get('user_profile')
    context.user_data.clear()
    context.user_data['user_profile'] = user_profile
    context.user_data['onboarding_data'] = {}

    # --- THIS IS THE V3 FIX ---
    # New first question, hardcoded bilingually, with explicit instructions.
    await (update.message or update.callback_query.message).reply_text(
        "Welcome to FinanceBot! Please select your language.\n"
        "Write `en` for English.\n\n"
        "សូមស្វាគមន៍មកកាន់ FinanceBot! សូមជ្រើសរើសភាសារបស់អ្នក។\n"
        "សរសេរ `km` សម្រាប់ភាសាខ្មែរ។",
        parse_mode='Markdown'
    )
    # --- END FIX ---
    log.info(f"User {user_id}: Sent language prompt. Awaiting state ASK_LANGUAGE.")
    return ASK_LANGUAGE


async def received_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles language selection and asks for currency mode."""
    user_id = update.effective_user.id
    choice = update.message.text.strip().lower()
    data = context.user_data['onboarding_data']
    log.info(f"User {user_id}: In state ASK_LANGUAGE. Received: '{choice}'")

    if choice not in ['en', 'km']:
        log.warning(f"User {user_id}: Invalid language choice.")
        await update.message.reply_text(
            "Invalid choice. Please reply with `en` or `km`.\n\n"
            "ការជ្រើសរើសមិនត្រឹមត្រូវ។ សូមឆ្លើយតបជាមួយ `en` ឬ `km` ។",
            parse_mode='Markdown'
        )
        return ASK_LANGUAGE

    data['language'] = choice
    context.user_data['user_profile']['settings']['language'] = choice
    log.info(f"User {user_id}: Set language to '{choice}'.")

    # Now that language is set, we can use the t() function
    await update.message.reply_text(t("onboarding.ask_mode", context))
    log.info(f"User {user_id}: Sent currency mode prompt. Awaiting state ASK_CURRENCY_MODE.")
    return ASK_CURRENCY_MODE


async def received_currency_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the '1' or '2' currency mode choice."""
    user_id = update.effective_user.id
    choice = update.message.text.strip()
    data = context.user_data['onboarding_data']
    log.info(f"User {user_id}: In state ASK_CURRENCY_MODE. Received: '{choice}'")

    if choice == '1':
        data['mode'] = 'single'
        log.info(f"User {user_id}: Set mode to 'single'.")
        # For single mode, we now only ask for EN name
        await update.message.reply_text(t("onboarding.ask_name_en", context))
        return ASK_NAME_EN

    elif choice == '2':
        data['mode'] = 'dual'
        log.info(f"User {user_id}: Set mode to 'dual'.")
        # For dual mode, we ask for both names
        await update.message.reply_text(t("onboarding.ask_name_en", context))
        return ASK_NAME_EN

    else:
        log.warning(f"User {user_id}: Invalid currency mode choice.")
        await update.message.reply_text(t("onboarding.invalid_mode", context))
        return ASK_CURRENCY_MODE


async def received_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the user's English name."""
    user_id = update.effective_user.id
    data = context.user_data['onboarding_data']
    data['name_en'] = update.message.text.strip()
    log.info(f"User {user_id}: Received EN name '{data['name_en']}'. Mode is '{data['mode']}'.")

    if data['mode'] == 'single':
        await update.message.reply_text(t("onboarding.ask_primary_currency", context))
        return ASK_SINGLE_CURRENCY

    elif data['mode'] == 'dual':
        await update.message.reply_text(t("onboarding.ask_name_km", context))
        return ASK_NAME_KM


async def received_name_km(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the user's Khmer name (dual mode)."""
    user_id = update.effective_user.id
    data = context.user_data['onboarding_data']
    data['name_km'] = update.message.text.strip()
    log.info(f"User {user_id}: Received KM name '{data['name_km']}'.")

    # Save mode, language, and names to DB
    api_client.update_user_mode(
        user_id,
        mode=data['mode'],
        language=data['language'],
        name_en=data['name_en'],
        name_km=data['name_km']
    )
    log.info(f"User {user_id}: Saved mode/names to DB.")

    # Update local cache
    context.user_data['user_profile']['name_en'] = data['name_en']
    context.user_data['user_profile']['name_km'] = data['name_km']
    context.user_data['user_profile']['settings']['currency_mode'] = data['mode']

    await update.message.reply_text(
        t("onboarding.ask_usd_balance", context, name=data['name_en'])
    )
    return ASK_USD_BALANCE


async def received_single_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the primary currency (single mode)."""
    user_id = update.effective_user.id
    data = context.user_data['onboarding_data']
    data['primary_currency'] = update.message.text.strip().upper()
    log.info(f"User {user_id}: Received single currency '{data['primary_currency']}'.")

    # Save mode, language, name, and currency to DB
    # --- THIS IS THE FIX for SyntaxError ---
    api_client.update_user_mode(
        user_id,
        mode=data['mode'],
        language=data['language'],
        name_en=data['name_en'],
        primary_currency=data['primary_currency']
    )
    # --- END FIX ---
    log.info(f"User {user_id}: Saved mode/names/currency to DB.")

    # Update local cache
    context.user_data['user_profile']['name_en'] = data['name_en']
    context.user_data['user_profile']['settings']['currency_mode'] = data['mode']
    context.user_data['user_profile']['settings']['primary_currency'] = data['primary_currency']

    await update.message.reply_text(
        t("onboarding.ask_single_balance", context,
          name=data['name_en'], currency=data['primary_currency'])
    )
    return ASK_SINGLE_BALANCE


async def received_usd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the initial USD balance (dual mode)."""
    user_id = update.effective_user.id
    try:
        amount = float(update.message.text)
        log.info(f"User {user_id}: Received USD balance '{amount}'.")

        api_client.update_initial_balance(user_id, 'USD', amount)
        context.user_data['user_profile']['settings']['initial_balances']['USD'] = amount

        await update.message.reply_text(
            t("onboarding.ask_khr_balance", context)
        )
        return ASK_KHR_BALANCE

    except (ValueError, TypeError):
        log.warning(f"User {user_id}: Invalid USD balance input.")
        await update.message.reply_text(
            t("onboarding.invalid_amount", context)
        )
        return ASK_USD_BALANCE
    except Exception as e:
        log.error(f"Error in received_usd_balance: {e}", exc_info=True)
        await update.message.reply_text(t("common.error_generic", context, error=e))
        return ConversationHandler.END


async def received_khr_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the initial KHR balance (dual mode) and ends onboarding."""
    user_id = update.effective_user.id
    try:
        # --- THIS IS THE FIX for circular import ---
        # from .common import start # <-- REMOVED
        # --- END FIX ---

        amount = float(update.message.text)
        log.info(f"User {user_id}: Received KHR balance '{amount}'.")

        api_client.update_initial_balance(user_id, 'KHR', amount)
        context.user_data['user_profile']['settings']['initial_balances']['KHR'] = amount

        # Mark onboarding as complete in the DB and local cache
        log.info(f"User {user_id}: Completing onboarding.")
        api_client.complete_onboarding(user_id)
        context.user_data['user_profile']['onboarding_complete'] = True

        await update.message.reply_text(
            t("onboarding.setup_complete", context)
        )
        # --- THIS IS THE FIX for circular import ---
        return ConversationHandler.END # <-- MODIFIED
        # --- END FIX ---

    except (ValueError, TypeError):
        log.warning(f"User {user_id}: Invalid KHR balance input.")
        await update.message.reply_text(
            t("onboarding.invalid_amount", context)
        )
        return ASK_KHR_BALANCE
    except Exception as e:
        log.error(f"Error in received_khr_balance: {e}", exc_info=True)
        await update.message.reply_text(t("common.error_generic", context, error=e))
        return ConversationHandler.END


async def received_single_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the initial balance (single mode) and ends onboarding."""
    user_id = update.effective_user.id
    try:
        # --- THIS IS THE FIX for circular import ---
        # from .common import start # <-- REMOVED
        # --- END FIX ---

        amount = float(update.message.text)
        currency = context.user_data['onboarding_data']['primary_currency']
        log.info(f"User {user_id}: Received single balance '{amount} {currency}'.")

        api_client.update_initial_balance(user_id, currency, amount)
        context.user_data['user_profile']['settings']['initial_balances'][currency] = amount

        # Mark onboarding as complete in the DB and local cache
        log.info(f"User {user_id}: Completing onboarding.")
        api_client.complete_onboarding(user_id)
        context.user_data['user_profile']['onboarding_complete'] = True

        await update.message.reply_text(
            t("onboarding.setup_complete", context)
        )
        # --- THIS IS THE FIX for circular import ---
        return ConversationHandler.END # <-- MODIFIED
        # --- END FIX ---


    except (ValueError, TypeError):
        log.warning(f"User {user_id}: Invalid single balance input.")
        await update.message.reply_text(
            t("onboarding.invalid_amount", context)
        )
        return ASK_SINGLE_BALANCE
    except Exception as e:
        log.error(f"Error in received_single_balance: {e}", exc_info=True)
        await update.message.reply_text(t("common.error_generic", context, error=e))
        return ConversationHandler.END


async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the onboarding process."""
    user_id = update.effective_user.id
    log.info(f"User {user_id}: Canceled onboarding.")
    await (update.message or update.callback_query.message).reply_text(
        t("common.cancel_onboarding", context)
    )
    context.user_data.clear()
    return ConversationHandler.END


onboarding_conversation_handler = ConversationHandler(
    entry_points=[
        # This handler is entered programmatically by the decorator
    ],
    states={
        ASK_LANGUAGE: [MessageHandler(
            filters.TEXT & ~filters.COMMAND, received_language
        )],
        ASK_CURRENCY_MODE: [MessageHandler(
            filters.TEXT & ~filters.COMMAND, received_currency_mode
        )],
        ASK_NAME_EN: [MessageHandler(
            filters.TEXT & ~filters.COMMAND, received_name_en
        )],
        ASK_NAME_KM: [MessageHandler(
            filters.TEXT & ~filters.COMMAND, received_name_km
        )],
        ASK_SINGLE_CURRENCY: [MessageHandler(
            filters.TEXT & ~filters.COMMAND, received_single_currency
        )],
        ASK_USD_BALANCE: [MessageHandler(
            filters.TEXT & ~filters.COMMAND, received_usd_balance
        )],
        ASK_KHR_BALANCE: [MessageHandler(
            filters.TEXT & ~filters.COMMAND, received_khr_balance
        )],
        ASK_SINGLE_BALANCE: [MessageHandler(
            filters.TEXT & ~filters.COMMAND, received_single_balance
        )],
    },
    fallbacks=[
        MessageHandler(filters.COMMAND, cancel_onboarding)
    ],
    per_message=False
)

# --- End of modified file ---