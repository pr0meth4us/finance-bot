# telegram_bot/handlers/onboarding.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
from utils.i18n import t
from decorators import authenticate_user
import keyboards

log = logging.getLogger(__name__)

(
    ASK_LANGUAGE,
    ASK_CURRENCY_MODE,
    ASK_NAME_EN,
    ASK_NAME_KM,
    ASK_SINGLE_CURRENCY,
    ASK_USD_BALANCE,
    ASK_KHR_BALANCE,
    ASK_SINGLE_BALANCE,
    ASK_SUBSCRIPTION,
    CONFIRM_RESET
) = range(100, 110)


@authenticate_user
async def onboarding_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Entry point for /start.
    Logic:
    - If user already onboarded -> Show 'Already Onboarded' message + End.
    - If new user -> Start Setup.
    """
    user_id = update.effective_user.id
    profile = context.user_data["profile"]

    if profile.get("onboarding_complete"):
        msg = t("onboarding.already_onboarded", context)
        await update.message.reply_text(msg, parse_mode='Markdown')
        return ConversationHandler.END

    # New user? Go straight to setup
    log.info(f"User {user_id}: Starting onboarding (First Time).")
    return await _start_setup_flow(update, context)


@authenticate_user
async def reset_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Entry point for /reset.
    Logic:
    - If user already onboarded -> Show Confirmation Warning -> Then Start Setup.
    - If new user -> Start Setup immediately.
    """
    user_id = update.effective_user.id
    profile = context.user_data["profile"]

    # Safety Check for existing users
    if profile.get("onboarding_complete"):
        log.info(f"User {user_id}: Triggered /reset. Asking confirmation.")

        text = t("onboarding.reset_warning", context)
        btn_yes = t("keyboards.reset_confirm", context)
        btn_no = t("keyboards.reset_cancel", context)

        keyboard = [
            [InlineKeyboardButton(btn_yes, callback_data='reset_confirm')],
            [InlineKeyboardButton(btn_no, callback_data='reset_cancel')]
        ]

        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return CONFIRM_RESET

    # If they haven't onboarded yet, /reset just acts like /start
    return await _start_setup_flow(update, context)


async def confirm_reset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'reset_cancel':
        await query.edit_message_text(t("onboarding.reset_cancelled", context))
        return ConversationHandler.END

    log.info(f"User {update.effective_user.id}: Confirmed reset.")
    return await _start_setup_flow(update, context)


async def _start_setup_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The actual setup logic (Language -> Mode -> Balance)."""
    context.user_data['onboarding_data'] = {}

    msg = (
        "Welcome to Savvify!\n"
        "Please select your language.\n"
        "➡️ For English, reply: en\n\n"
        "សូមស្វាគមន៍មកកាន់ Savvify!\n"
        "សូមជ្រើសរើសភាសា។\n"
        "➡️ សម្រាប់ភាសាខ្មែរ សូមឆ្លើយតប៖ km"
    )

    if update.callback_query:
        await update.callback_query.message.reply_text(msg)
    else:
        await update.message.reply_text(msg)

    return ASK_LANGUAGE


# --- Step Handlers ---

async def received_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip().lower()
    if choice not in ['en', 'km']:
        await update.message.reply_text("Invalid choice. Reply `en` or `km`.\nមិនត្រឹមត្រូវទេ។ សូមឆ្លើយ `en` ឬ `km`។")
        return ASK_LANGUAGE

    context.user_data['onboarding_data']['language'] = choice
    context.user_data['profile']['settings']['language'] = choice

    await update.message.reply_text(t("onboarding.ask_mode", context))
    return ASK_CURRENCY_MODE


async def received_currency_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    data = context.user_data['onboarding_data']
    lang = data['language']

    if choice == '1':
        data['mode'] = 'single'
        prompt_key = "onboarding.ask_name_km" if lang == 'km' else "onboarding.ask_name_en"
        next_state = ASK_NAME_KM if lang == 'km' else ASK_NAME_EN
    elif choice == '2':
        data['mode'] = 'dual'
        prompt_key = "onboarding.ask_name_km" if lang == 'km' else "onboarding.ask_name_en"
        next_state = ASK_NAME_KM if lang == 'km' else ASK_NAME_EN
    else:
        await update.message.reply_text(t("onboarding.invalid_mode", context))
        return ASK_CURRENCY_MODE

    await update.message.reply_text(t(prompt_key, context))
    return next_state


async def received_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['onboarding_data']
    data['name_en'] = update.message.text.strip()

    if data['mode'] == 'single':
        await update.message.reply_text(t("onboarding.ask_primary_currency", context))
        return ASK_SINGLE_CURRENCY
    else:
        if 'name_km' not in data:
            await update.message.reply_text(t("onboarding.ask_name_km", context))
            return ASK_NAME_KM
        return await _save_mode_and_names(update, context)


async def received_name_km(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['onboarding_data']
    data['name_km'] = update.message.text.strip()

    if data['mode'] == 'single':
        await update.message.reply_text(t("onboarding.ask_primary_currency", context))
        return ASK_SINGLE_CURRENCY
    else:
        if 'name_en' not in data:
            await update.message.reply_text(t("onboarding.ask_name_en", context))
            return ASK_NAME_EN
        return await _save_mode_and_names(update, context)


async def _save_mode_and_names(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['onboarding_data']
    jwt = context.user_data['jwt']

    api_client.update_user_mode(
        jwt,
        mode=data['mode'],
        language=data['language'],
        name_en=data.get('name_en'),
        name_km=data.get('name_km')
    )

    profile = context.user_data['profile']
    profile['name_en'] = data.get('name_en')
    profile['name_km'] = data.get('name_km')
    profile['settings']['currency_mode'] = data['mode']

    display_name = data.get('name_km') if data['language'] == 'km' else data.get('name_en')
    await update.message.reply_text(t("onboarding.ask_usd_balance", context, name=display_name))
    return ASK_USD_BALANCE


async def received_single_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['onboarding_data']
    jwt = context.user_data['jwt']
    currency = update.message.text.strip().upper()
    data['primary_currency'] = currency

    api_client.update_user_mode(
        jwt,
        mode=data['mode'],
        language=data['language'],
        name_en=data.get('name_en'),
        name_km=data.get('name_km'),
        primary_currency=currency
    )

    profile = context.user_data['profile']
    profile['name_en'] = data.get('name_en')
    profile['name_km'] = data.get('name_km')
    profile['settings']['currency_mode'] = data['mode']
    profile['settings']['primary_currency'] = currency

    display_name = data.get('name_en') or data.get('name_km')
    await update.message.reply_text(t("onboarding.ask_single_balance", context, name=display_name, currency=currency))
    return ASK_SINGLE_BALANCE


async def received_usd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        api_client.update_initial_balance(context.user_data['jwt'], 'USD', amount)
        context.user_data['profile']['settings']['initial_balances']['USD'] = amount

        await update.message.reply_text(t("onboarding.ask_khr_balance", context))
        return ASK_KHR_BALANCE
    except ValueError:
        await update.message.reply_text(t("onboarding.invalid_amount", context))
        return ASK_USD_BALANCE


async def received_khr_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        jwt = context.user_data['jwt']

        api_client.update_initial_balance(jwt, 'KHR', amount)
        context.user_data['profile']['settings']['initial_balances']['KHR'] = amount

        # Proceed to Subscription Step
        await update.message.reply_text(
            t("onboarding.ask_subscription", context),
            parse_mode='HTML',
            reply_markup=keyboards.subscription_tier_keyboard(context)
        )
        return ASK_SUBSCRIPTION
    except ValueError:
        await update.message.reply_text(t("onboarding.invalid_amount", context))
        return ASK_KHR_BALANCE


async def received_single_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        currency = context.user_data['onboarding_data']['primary_currency']
        jwt = context.user_data['jwt']

        api_client.update_initial_balance(jwt, currency, amount)
        context.user_data['profile']['settings']['initial_balances'][currency] = amount

        # Proceed to Subscription Step
        await update.message.reply_text(
            t("onboarding.ask_subscription", context),
            parse_mode='Markdown',
            reply_markup=keyboards.subscription_tier_keyboard(context)
        )
        return ASK_SUBSCRIPTION
    except ValueError:
        await update.message.reply_text(t("onboarding.invalid_amount", context))
        return ASK_SINGLE_BALANCE


async def received_subscription_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    # This is a mock step for now since actual payment logic isn't provided.
    # If they choose premium, we just tell them to contact admin, then finish.
    jwt = context.user_data['jwt']

    if choice == 'plan_premium':
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=t("common.premium_required", context) + "\n\nFor now, you are on the Free plan."
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✅ Selected Free Plan."
        )

    # Finalize
    api_client.complete_onboarding(jwt)
    context.user_data['profile']['onboarding_complete'] = True
    if 'profile_data' in context.user_data:
        context.user_data['profile_data']['profile']['onboarding_complete'] = True

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=t("onboarding.setup_complete", context),
        reply_markup=keyboards.main_menu_keyboard(context)
    )
    return ConversationHandler.END


async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await (update.message or update.callback_query.message).reply_text(t("common.cancel_onboarding", context))
    return ConversationHandler.END


onboarding_conversation_handler = ConversationHandler(
    entry_points=[
        CommandHandler('start', onboarding_start),
        CommandHandler('reset', reset_start),
        CallbackQueryHandler(onboarding_start, pattern='^start$')
    ],
    states={
        # CONFIRM RESET
        CONFIRM_RESET: [CallbackQueryHandler(confirm_reset_callback, pattern='^reset_')],

        ASK_LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_language)],
        ASK_CURRENCY_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_currency_mode)],
        ASK_NAME_EN: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_name_en)],
        ASK_NAME_KM: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_name_km)],
        ASK_SINGLE_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_single_currency)],
        ASK_USD_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_usd_balance)],
        ASK_KHR_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_khr_balance)],
        ASK_SINGLE_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_single_balance)],
        # NEW: Subscription Step
        ASK_SUBSCRIPTION: [CallbackQueryHandler(received_subscription_choice, pattern='^plan_')]
    },
    fallbacks=[CommandHandler('cancel', cancel_onboarding)],
    per_message=False
)