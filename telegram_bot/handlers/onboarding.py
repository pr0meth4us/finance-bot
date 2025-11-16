# --- telegram_bot/handlers/onboarding.py (Refactored) ---

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    CommandHandler
)
import logging
import api_client
import keyboards
from .helpers import format_summary_message
from utils.i18n import t
from decorators import authenticate_user  # Import the decorator

log = logging.getLogger(__name__)

# Conversation states
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


@authenticate_user  # --- REFACTOR: Decorator is now used ---
async def onboarding_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Starts the mandatory onboarding flow OR shows the main menu.
    This is the main entry point for /start.
    The @authenticate_user decorator handles profile/JWT fetching.
    """
    user_id = update.effective_user.id
    log.info(f"User {user_id}: Entering onboarding_start (from /start or callback).")

    # Decorator has already run, so profile_data is guaranteed to be in cache
    # unless auth failed (in which case this handler wouldn't be called).
    profile_data = context.user_data["profile_data"]
    profile = profile_data.get("profile", {})
    is_complete = profile.get("onboarding_complete")

    jwt = context.user_data["jwt"]  # Get JWT from decorator

    if is_complete:
        # User is onboarded, just call the normal start handler logic
        log.info(f"User {user_id}: Already onboarded. Showing main menu.")

        lang = profile.get('settings', {}).get('language', 'en')
        user_name = profile.get('name_en', 'User')
        if lang == 'km' and profile.get('name_km'):
            user_name = profile.get('name_km')

        text = t("common.welcome", context, name=user_name)
        keyboard = keyboards.main_menu_keyboard(context)
        chat_id = update.effective_chat.id

        # --- REFACTOR: Pass JWT ---
        summary_data = api_client.get_detailed_summary(jwt)
        summary_text = format_summary_message(summary_data, context)

        if update.callback_query:
            await update.callback_query.answer()
            try:
                await update.callback_query.edit_message_text(
                    text + summary_text, parse_mode='HTML', reply_markup=keyboard
                )
            except Exception:
                pass  # Message might be identical
        else:
            await context.bot.send_message(
                chat_id=chat_id, text=text + summary_text, parse_mode='HTML', reply_markup=keyboard
            )
        return ConversationHandler.END  # End the conversation

    # --- START ONBOARDING FLOW ---
    log.info(f"User {user_id}: Not onboarded. Starting flow.")

    # --- THIS IS THE FIX ---
    # The decorator ALREADY populated the cache.
    # We MUST NOT clear it. We only need to add the 'onboarding_data' key.
    context.user_data['onboarding_data'] = {}
    # --- END FIX ---

    message_interface = update.message
    if update.callback_query:
        await update.callback_query.answer()
        message_interface = update.callback_query.message
    else:
        message_interface = update.message

    await message_interface.reply_text(
        "Welcome to FinanceBot! Please select your language.\n"
        "➡️ For English, reply: en\n\n"
        "សូមស្វាគមន៍មកកាន់ FinanceBot! សូមជ្រើសរើសភាសា។\n"
        "➡️ សម្រាប់ភាសាខ្មែរ សូមឆ្លើយតប៖ km"
    )
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
    # --- REFACTOR: Update profile cache in context for t() to work ---
    context.user_data['profile']['settings']['language'] = choice
    log.info(f"User {user_id}: Set language to '{choice}'.")

    await update.message.reply_text(t("onboarding.ask_mode", context))
    log.info(f"User {user_id}: Sent currency mode prompt. Awaiting state ASK_CURRENCY_MODE.")
    return ASK_CURRENCY_MODE


async def received_currency_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the '1' or '2' currency mode choice."""
    user_id = update.effective_user.id
    choice = update.message.text.strip()
    data = context.user_data['onboarding_data']
    lang = data['language']
    log.info(f"User {user_id}: In state ASK_CURRENCY_MODE. Received: '{choice}'")

    next_state = None
    prompt = ""

    if choice == '1':
        data['mode'] = 'single'
        log.info(f"User {user_id}: Set mode to 'single'.")
        if lang == 'km':
            prompt = t("onboarding.ask_name_km", context)
            next_state = ASK_NAME_KM
        else:
            prompt = t("onboarding.ask_name_en", context)
            next_state = ASK_NAME_EN

    elif choice == '2':
        data['mode'] = 'dual'
        log.info(f"User {user_id}: Set mode to 'dual'.")
        if lang == 'km':
            prompt = t("onboarding.ask_name_km", context)
            next_state = ASK_NAME_KM
        else:
            prompt = t("onboarding.ask_name_en", context)
            next_state = ASK_NAME_EN

    else:
        log.warning(f"User {user_id}: Invalid currency mode choice.")
        await update.message.reply_text(t("onboarding.invalid_mode", context))
        return ASK_CURRENCY_MODE

    await update.message.reply_text(prompt)
    return next_state


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
        if 'name_km' not in data:
            await update.message.reply_text(t("onboarding.ask_name_km", context))
            return ASK_NAME_KM
        else:
            return await _save_mode_and_names(update, context)


async def received_name_km(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the user's Khmer name."""
    user_id = update.effective_user.id
    data = context.user_data['onboarding_data']
    data['name_km'] = update.message.text.strip()
    log.info(f"User {user_id}: Received KM name '{data['name_km']}'.")

    if data['mode'] == 'single':
        await update.message.reply_text(t("onboarding.ask_primary_currency", context))
        return ASK_SINGLE_CURRENCY

    elif data['mode'] == 'dual':
        if 'name_en' not in data:
            await update.message.reply_text(t("onboarding.ask_name_en", context))
            return ASK_NAME_EN
        else:
            return await _save_mode_and_names(update, context)


async def _save_mode_and_names(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Internal helper to save mode/names (for DUAL mode) and ask for USD balance.
    """
    user_id = update.effective_user.id
    data = context.user_data['onboarding_data']
    jwt = context.user_data['jwt']  # --- REFACTOR: Get JWT ---
    log.info(f"User {user_id}: Saving dual-mode names.")

    # --- REFACTOR: Pass JWT ---
    api_client.update_user_mode(
        jwt,
        mode=data['mode'],
        language=data['language'],
        name_en=data['name_en'],
        name_km=data['name_km']
    )
    log.info(f"User {user_id}: Saved mode/names to DB.")

    # Update local cache
    context.user_data['profile']['name_en'] = data['name_en']
    context.user_data['profile']['name_km'] = data['name_km']
    context.user_data['profile']['settings']['currency_mode'] = data['mode']

    lang = data['language']
    display_name = data.get('name_km') if lang == 'km' else data.get('name_en')

    await update.message.reply_text(
        t("onboarding.ask_usd_balance", context, name=display_name)
    )
    return ASK_USD_BALANCE


async def received_single_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the primary currency (single mode)."""
    user_id = update.effective_user.id
    data = context.user_data['onboarding_data']
    jwt = context.user_data['jwt']  # --- REFACTOR: Get JWT ---
    data['primary_currency'] = update.message.text.strip().upper()
    log.info(f"User {user_id}: Received single currency '{data['primary_currency']}'.")

    name_en = data.get('name_en')
    name_km = data.get('name_km')

    # --- REFACTOR: Pass JWT ---
    api_client.update_user_mode(
        jwt,
        mode=data['mode'],
        language=data['language'],
        name_en=name_en,
        name_km=name_km,
        primary_currency=data['primary_currency']
    )
    log.info(f"User {user_id}: Saved mode/names/currency to DB.")

    # Update local cache
    if name_en:
        context.user_data['profile']['name_en'] = name_en
    if name_km:
        context.user_data['profile']['name_km'] = name_km
    context.user_data['profile']['settings']['currency_mode'] = data['mode']
    context.user_data['profile']['settings']['primary_currency'] = data['primary_currency']

    display_name = name_en or name_km
    await update.message.reply_text(
        t("onboarding.ask_single_balance", context,
          name=display_name, currency=data['primary_currency'])
    )
    return ASK_SINGLE_BALANCE


async def received_usd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the initial USD balance (dual mode)."""
    user_id = update.effective_user.id
    jwt = context.user_data['jwt']  # --- REFACTOR: Get JWT ---
    try:
        amount = float(update.message.text)
        log.info(f"User {user_id}: Received USD balance '{amount}'.")

        # --- REFACTOR: Pass JWT ---
        api_client.update_initial_balance(jwt, 'USD', amount)
        context.user_data['profile']['settings']['initial_balances']['USD'] = amount

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
    jwt = context.user_data['jwt']  # --- REFACTOR: Get JWT ---
    try:
        amount = float(update.message.text)
        log.info(f"User {user_id}: Received KHR balance '{amount}'.")

        # --- REFACTOR: Pass JWT ---
        api_client.update_initial_balance(jwt, 'KHR', amount)
        context.user_data['profile']['settings']['initial_balances']['KHR'] = amount

        log.info(f"User {user_id}: Completing onboarding.")
        # --- REFACTOR: Pass JWT ---
        api_client.complete_onboarding(jwt)
        context.user_data['profile']['onboarding_complete'] = True

        # Manually update the profile_data cache as well
        if 'profile_data' in context.user_data:
            context.user_data['profile_data']['profile']['onboarding_complete'] = True

        await update.message.reply_text(
            t("onboarding.setup_complete", context)
        )
        return await onboarding_start(update, context)

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
    jwt = context.user_data['jwt']  # --- REFACTOR: Get JWT ---
    try:
        amount = float(update.message.text)
        currency = context.user_data['onboarding_data']['primary_currency']
        log.info(f"User {user_id}: Received single balance '{amount} {currency}'.")

        # --- REFACTOR: Pass JWT ---
        api_client.update_initial_balance(jwt, currency, amount)
        context.user_data['profile']['settings']['initial_balances'][currency] = amount

        log.info(f"User {user_id}: Completing onboarding.")
        # --- REFACTOR: Pass JWT ---
        api_client.complete_onboarding(jwt)
        context.user_data['profile']['onboarding_complete'] = True

        # Manually update the profile_data cache as well
        if 'profile_data' in context.user_data:
            context.user_data['profile_data']['profile']['onboarding_complete'] = True

        await update.message.reply_text(
            t("onboarding.setup_complete", context)
        )
        return await onboarding_start(update, context)

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
        CommandHandler('start', onboarding_start),
        CallbackQueryHandler(onboarding_start, pattern='^start$')
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
        CommandHandler('cancel', cancel_onboarding),
        MessageHandler(filters.COMMAND, cancel_onboarding)
    ],
    per_message=False
)