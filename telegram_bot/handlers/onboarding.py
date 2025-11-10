# --- telegram_bot/handlers/onboarding.py (FULL) ---

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


async def onboarding_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Starts the mandatory onboarding flow OR shows the main menu.
    This is the main entry point for /start.
    """
    user_id_str = update.effective_user.id
    log.info(f"User {user_id_str}: Entering onboarding_start (from /start or callback).")

    if not update.effective_user:
        log.warning("onboarding_start received update with no effective_user.")
        return ConversationHandler.END

    cached = context.user_data.get("user_profile")
    if not cached:
        log.info(f"User {user_id_str}: No profile in cache. Fetching from API.")
        # Use the Telegram ID (string) for auth
        profile = api_client.find_or_create_user(user_id_str)
        if not profile or profile.get("error"):
            msg = profile.get("error", "Auth failed.")
            log.error(f"User {user_id_str}: Auth failed or API error: {msg}")
            if update.message:
                await update.message.reply_text(f"🚫 {msg}")
            elif update.callback_query:
                await context.bot.answer_callback_query(update.callback_query.id, f"🚫 {msg}", show_alert=True)
            return ConversationHandler.END
        context.user_data["user_profile"] = profile
        log.info(f"User {user_id_str}: Profile fetched and cached.")
    else:
        log.info(f"User {user_id_str}: Profile found in cache.")

    is_complete = context.user_data["user_profile"].get("onboarding_complete")

    if is_complete:
        # --- REPLICATE common.start LOGIC ---
        log.info(f"User {user_id_str}: Already onboarded. Showing main menu.")
        user_profile = context.user_data['user_profile']
        # --- THIS IS THE KEY ---
        # Get the MONGO _id for API calls
        user_id_obj = user_profile['_id']
        # ---

        lang = user_profile.get('settings', {}).get('language', 'en')
        user_name = user_profile.get('name_en', 'User')
        if lang == 'km' and user_profile.get('name_km'):
            user_name = user_profile.get('name_km')

        text = t("common.welcome", context, name=user_name)
        keyboard = keyboards.main_menu_keyboard(context)
        chat_id = update.effective_chat.id

        # Use the Mongo _id for the summary call
        summary_data = api_client.get_detailed_summary(user_id_obj)
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
        # --- END REPLICATE ---

    # --- START ONBOARDING FLOW ---
    log.info(f"User {user_id_str}: Not onboarded. Starting flow.")
    user_profile = context.user_data.get('user_profile')
    context.user_data.clear()
    context.user_data['user_profile'] = user_profile
    context.user_data['onboarding_data'] = {}

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

    log.info(f"User {user_id_str}: Sent language prompt. Awaiting state ASK_LANGUAGE.")
    return ASK_LANGUAGE


async def received_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles language selection and asks for currency mode."""
    user_id_str = update.effective_user.id
    choice = update.message.text.strip().lower()
    data = context.user_data['onboarding_data']
    log.info(f"User {user_id_str}: In state ASK_LANGUAGE. Received: '{choice}'")

    if choice not in ['en', 'km']:
        log.warning(f"User {user_id_str}: Invalid language choice.")
        await update.message.reply_text(
            "Invalid choice. Please reply with `en` or `km`.\n\n"
            "ការជ្រើសរើសមិនត្រឹមត្រូវ។ សូមឆ្លើយតបជាមួយ `en` ឬ `km` ។",
            parse_mode='Markdown'
        )
        return ASK_LANGUAGE

    data['language'] = choice
    context.user_data['user_profile']['settings']['language'] = choice
    log.info(f"User {user_id_str}: Set language to '{choice}'.")

    await update.message.reply_text(t("onboarding.ask_mode", context))
    log.info(f"User {user_id_str}: Sent currency mode prompt. Awaiting state ASK_CURRENCY_MODE.")
    return ASK_CURRENCY_MODE


async def received_currency_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the '1' or '2' currency mode choice."""
    user_id_str = update.effective_user.id
    choice = update.message.text.strip()
    data = context.user_data['onboarding_data']
    log.info(f"User {user_id_str}: In state ASK_CURRENCY_MODE. Received: '{choice}'")

    if choice == '1':
        data['mode'] = 'single'
        log.info(f"User {user_id_str}: Set mode to 'single'.")
        await update.message.reply_text(t("onboarding.ask_name_en", context))
        return ASK_NAME_EN

    elif choice == '2':
        data['mode'] = 'dual'
        log.info(f"User {user_id_str}: Set mode to 'dual'.")
        await update.message.reply_text(t("onboarding.ask_name_en", context))
        return ASK_NAME_EN

    else:
        log.warning(f"User {user_id_str}: Invalid currency mode choice.")
        await update.message.reply_text(t("onboarding.invalid_mode", context))
        return ASK_CURRENCY_MODE


async def received_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the user's English name."""
    user_id_str = update.effective_user.id
    data = context.user_data['onboarding_data']
    data['name_en'] = update.message.text.strip()
    log.info(f"User {user_id_str}: Received EN name '{data['name_en']}'. Mode is '{data['mode']}'.")

    if data['mode'] == 'single':
        await update.message.reply_text(t("onboarding.ask_primary_currency", context))
        return ASK_SINGLE_CURRENCY

    elif data['mode'] == 'dual':
        await update.message.reply_text(t("onboarding.ask_name_km", context))
        return ASK_NAME_KM


async def received_name_km(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles receiving the user's Khmer name (dual mode)."""
    # --- THIS IS THE FIX ---
    # Get the MONGO _id from the cache
    user_id = context.user_data['user_profile']['_id']
    # ---
    data = context.user_data['onboarding_data']
    data['name_km'] = update.message.text.strip()
    log.info(f"User {user_id}: Received KM name '{data['name_km']}'.")

    # Save mode, language, and names to DB
    api_client.update_user_mode(
        user_id,  # Use Mongo _id
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
    # --- THIS IS THE FIX ---
    # Get the MONGO _id from the cache
    user_id = context.user_data['user_profile']['_id']
    # ---
    data = context.user_data['onboarding_data']
    data['primary_currency'] = update.message.text.strip().upper()
    log.info(f"User {user_id}: Received single currency '{data['primary_currency']}'.")

    api_client.update_user_mode(
        user_id,  # Use Mongo _id
        mode=data['mode'],
        language=data['language'],
        name_en=data['name_en'],
        primary_currency=data['primary_currency']
    )
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
    # --- THIS IS THE FIX ---
    # Get the MONGO _id from the cache
    user_id = context.user_data['user_profile']['_id']
    # ---
    try:
        amount = float(update.message.text)
        log.info(f"User {user_id}: Received USD balance '{amount}'.")

        api_client.update_initial_balance(user_id, 'USD', amount)  # Use Mongo _id
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
    # --- THIS IS THE FIX ---
    # Get the MONGO _id from the cache
    user_id = context.user_data['user_profile']['_id']
    # ---
    try:
        amount = float(update.message.text)
        log.info(f"User {user_id}: Received KHR balance '{amount}'.")

        api_client.update_initial_balance(user_id, 'KHR', amount)  # Use Mongo _id
        context.user_data['user_profile']['settings']['initial_balances']['KHR'] = amount

        # Mark onboarding as complete in the DB and local cache
        log.info(f"User {user_id}: Completing onboarding.")
        api_client.complete_onboarding(user_id)  # Use Mongo _id
        context.user_data['user_profile']['onboarding_complete'] = True

        await update.message.reply_text(
            t("onboarding.setup_complete", context)
        )
        # Manually call the start logic again to show the main menu
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
    # --- THIS IS THE FIX ---
    # Get the MONGO _id from the cache
    user_id = context.user_data['user_profile']['_id']
    # ---
    try:
        amount = float(update.message.text)
        currency = context.user_data['onboarding_data']['primary_currency']
        log.info(f"User {user_id}: Received single balance '{amount} {currency}'.")

        api_client.update_initial_balance(user_id, currency, amount)  # Use Mongo _id
        context.user_data['user_profile']['settings']['initial_balances'][currency] = amount

        # Mark onboarding as complete in the DB and local cache
        log.info(f"User {user_id}: Completing onboarding.")
        api_client.complete_onboarding(user_id)  # Use Mongo _id
        context.user_data['user_profile']['onboarding_complete'] = True

        await update.message.reply_text(
            t("onboarding.setup_complete", context)
        )
        # Manually call the start logic again to show the main menu
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
        CommandHandler('start', onboarding_start),  # <-- MODIFIED: This is now the main entry
        CallbackQueryHandler(onboarding_start, pattern='^start$')  # <-- NEW: Catches 'back' buttons
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
        # Allow /cancel during onboarding
        CommandHandler('cancel', cancel_onboarding),
        # Also catch any other command
        MessageHandler(filters.COMMAND, cancel_onboarding)
    ],
    per_message=False
)
# --- End of modified file ---