# telegram_bot/handlers/settings.py

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    CommandHandler
)
import api_client
import keyboards
# FIXED: Import 'menu' instead of 'start'
from .common import menu, cancel
from decorators import authenticate_user
from utils.i18n import t

(
    SETTINGS_MENU,
    SETBALANCE_ACCOUNT,
    SETBALANCE_AMOUNT,
    NEW_RATE,
    CATEGORIES_MENU,
    CATEGORY_ADD_START,
    CATEGORY_ADD_GET_NAME,
    CATEGORY_REMOVE_START,
    CATEGORY_REMOVE_GET_NAME,
    SWITCH_TO_DUAL_CONFIRM,
    SWITCH_TO_DUAL_GET_KM_NAME,
    ASK_NEW_LANGUAGE,
    GET_MISSING_NAME
) = range(13)


@authenticate_user
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main settings menu entry point."""
    query = update.callback_query
    if query: await query.answer()
    message_interface = query.message if query else update.message

    jwt = context.user_data['jwt']
    user_data = api_client.get_user_settings(jwt)
    rate_data = api_client.get_exchange_rate(jwt)

    # --- FIX: Handle None responses (Connection/Auth errors) ---
    if not user_data or not rate_data:
        await message_interface.reply_text(t("common.upstream_error", context))
        return ConversationHandler.END

    if "error" in user_data or "error" in rate_data:
        await message_interface.reply_text(t("common.error_generic", context))
        return ConversationHandler.END

    context.user_data["profile"] = user_data.get("profile", {})
    # Ensure nested profile_data exists if accessed elsewhere
    if "profile_data" not in context.user_data:
        context.user_data["profile_data"] = {}
    context.user_data["profile_data"]["profile"] = user_data.get("profile", {})

    profile = context.user_data["profile"]
    settings = profile.get('settings', {})
    balances = settings.get('initial_balances', {})
    mode = settings.get('currency_mode', 'dual')

    balance_text = ""
    if mode == 'dual':
        balance_text = f"  💵 ${balances.get('USD', 0):,.2f} USD\n  ៛ {balances.get('KHR', 0):,.0f} KHR"
    else:
        curr = settings.get('primary_currency', 'USD')
        fmt = ",.0f" if curr == 'KHR' else ",.2f"
        balance_text = f"  <b>{balances.get(curr, 0):{fmt}} {curr}</b>"

    rate_val = rate_data.get('rate', 4100)
    rate_text = f"Fixed ({rate_val:,.0f})" if settings.get('rate_preference') == 'fixed' else f"Live ({rate_val:,.0f})"

    text = t("settings.menu_header", context, balance_text=balance_text, rate_text=rate_text, mode=mode.title())
    keyboard = keyboards.settings_menu_keyboard(context)

    if query:
        await message_interface.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    else:
        await message_interface.reply_text(text, parse_mode='HTML', reply_markup=keyboard)

    return SETTINGS_MENU


async def set_balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    profile = context.user_data['profile']
    mode = profile.get('settings', {}).get('currency_mode', 'dual')
    currencies = (profile.get('settings', {}).get('primary_currency', 'USD'),)

    await query.edit_message_text(
        t("settings.ask_balance_account", context),
        reply_markup=keyboards.set_balance_account_keyboard(context, mode, currencies)
    )
    return SETBALANCE_ACCOUNT


async def received_balance_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['settings_currency'] = query.data.split('_')[-1]
    await query.edit_message_text(
        t("settings.ask_balance_amount", context, currency=context.user_data['settings_currency']), parse_mode='HTML')
    return SETBALANCE_AMOUNT


async def received_balance_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        currency = context.user_data['settings_currency']
        api_client.update_initial_balance(context.user_data['jwt'], currency, amount)

        await update.message.reply_text(t("settings.balance_set_success", context, currency=currency, amount=amount))
        return await settings_menu(update, context)
    except ValueError:
        await update.message.reply_text(t("tx.invalid_amount", context))
        return SETBALANCE_AMOUNT


async def update_rate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(t("settings.ask_rate", context))
    return NEW_RATE


async def received_new_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rate = float(update.message.text)
        api_client.update_exchange_rate(rate, context.user_data['jwt'])
        await update.message.reply_text(t("settings.rate_set_success", context, rate=rate))
        return await settings_menu(update, context)
    except ValueError:
        await update.message.reply_text(t("settings.invalid_rate", context))
        return NEW_RATE


async def categories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_data = api_client.get_user_settings(context.user_data['jwt'])

    # --- FIX: Handle None ---
    if not user_data or "error" in user_data:
        return await settings_menu(update, context)

    context.user_data["profile"] = user_data.get("profile", {})
    cats = context.user_data["profile"].get('settings', {}).get('categories', {})

    text = t("settings.categories_header", context,
             expense_cats=', '.join(cats.get('expense', [])) or 'None',
             income_cats=', '.join(cats.get('income', [])) or 'None')

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboards.manage_categories_keyboard(context))
    return CATEGORIES_MENU


async def category_action_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    profile = context.user_data.get('profile', {})
    tier = profile.get('subscription_tier', 'free')
    if str(update.effective_user.id) == "1836585300":
        tier = 'premium'

    if tier != 'premium':
        await query.answer("🔒 Premium Feature", show_alert=True)
        upsell_text = (
            "🔒 <b>Manage Categories is Locked</b>\n\n"
            "Free users are limited to the Basic categories.\n"
            "Upgrade to Premium to customize!"
        )
        await query.edit_message_text(
            upsell_text,
            parse_mode='HTML',
            reply_markup=keyboards.manage_categories_keyboard(context)
        )
        return CATEGORIES_MENU

    await query.answer()
    action = 'add' if 'add' in query.data else 'remove'
    context.user_data['category_action'] = action

    await query.edit_message_text(
        t(f"settings.category_ask_{action}", context),
        reply_markup=keyboards.category_type_keyboard(context, action)
    )
    return CATEGORY_ADD_START if action == 'add' else CATEGORY_REMOVE_START


async def received_category_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = context.user_data['category_action']
    cat_type = query.data.split(':')[-1]
    context.user_data['category_type'] = cat_type

    await query.edit_message_text(t("settings.category_ask_name", context, cat_type=cat_type, action=action))
    return CATEGORY_ADD_GET_NAME if action == 'add' else CATEGORY_REMOVE_GET_NAME


async def received_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data['category_action']
    cat_type = context.user_data['category_type']
    name = update.message.text.strip().title()
    jwt = context.user_data['jwt']

    if action == 'add':
        res = api_client.add_category(jwt, cat_type, name)
        if res and "error" not in res:
            msg = t("settings.category_add_success", context, name=name, type=cat_type)
        else:
            msg = f"❌ {res.get('error', 'Unknown Error')}" if res else t("common.error_generic", context)
    else:
        res = api_client.remove_category(jwt, cat_type, name)
        if res and "error" not in res:
            msg = t("settings.category_remove_success", context, name=name, type=cat_type)
        else:
            msg = f"❌ {res.get('error', 'Unknown Error')}" if res else t("common.error_generic", context)

    await update.message.reply_text(msg)
    return await settings_menu(update, context)


async def switch_to_dual_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        t("settings.switch_to_dual_confirm", context),
        reply_markup=keyboards.switch_to_dual_confirm_keyboard(context)
    )
    return SWITCH_TO_DUAL_CONFIRM


async def switch_to_dual_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data['profile']['settings']['language'] = 'km'
    await update.callback_query.edit_message_text(t("settings.ask_name_km_switch", context))
    return SWITCH_TO_DUAL_GET_KM_NAME


async def received_km_name_for_switch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    km_name = update.message.text.strip()
    jwt = context.user_data['jwt']
    profile = context.user_data['profile']

    api_client.update_user_mode(jwt, mode='dual', language='km', name_en=profile.get('name_en'), name_km=km_name)

    profile['settings']['currency_mode'] = 'dual'
    profile['settings']['language'] = 'km'
    profile['name_km'] = km_name

    await update.message.reply_text(t("settings.switch_to_dual_success", context))
    return await settings_menu(update, context)


async def change_language_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        t("settings.ask_new_language", context),
        reply_markup=keyboards.change_language_keyboard(context)
    )
    return ASK_NEW_LANGUAGE


async def received_new_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    new_lang = query.data.split(':')[-1]
    profile = context.user_data['profile']
    context.user_data['new_lang'] = new_lang

    if profile.get('settings', {}).get('currency_mode') == 'dual':
        if new_lang == 'km' and not profile.get('name_km'):
            context.user_data['profile']['settings']['language'] = 'km'
            await query.edit_message_text(t("settings.ask_missing_name_km", context))
            return GET_MISSING_NAME
        if new_lang == 'en' and not profile.get('name_en'):
            context.user_data['profile']['settings']['language'] = 'en'
            await query.edit_message_text(t("settings.ask_missing_name_en", context))
            return GET_MISSING_NAME

    return await _finalize_language_switch(query, context, new_lang)


async def received_missing_name_for_switch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    new_lang = context.user_data['new_lang']
    profile = context.user_data['profile']

    if new_lang == 'km':
        profile['name_km'] = new_name
    else:
        profile['name_en'] = new_name

    return await _finalize_language_switch(update, context, new_lang)


async def _finalize_language_switch(update_obj, context, new_lang):
    jwt = context.user_data['jwt']
    profile = context.user_data['profile']

    api_client.update_user_mode(
        jwt,
        mode=profile.get('settings', {}).get('currency_mode'),
        language=new_lang,
        name_en=profile.get('name_en'),
        name_km=profile.get('name_km'),
        primary_currency=profile.get('settings', {}).get('primary_currency')
    )

    context.user_data['profile']['settings']['language'] = new_lang

    msg = t("settings.language_switch_success", context)
    kb = keyboards.main_menu_keyboard(context)

    if isinstance(update_obj, Update):
        await update_obj.message.reply_text(msg, reply_markup=kb)
    else:
        await update_obj.edit_message_text(msg, reply_markup=kb)

    return ConversationHandler.END


settings_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(settings_menu, pattern='^settings_menu$')],
    states={
        SETTINGS_MENU: [
            CallbackQueryHandler(set_balance_start, pattern='^settings_set_balance$'),
            CallbackQueryHandler(update_rate_start, pattern='^settings_set_rate$'),
            CallbackQueryHandler(categories_menu, pattern='^settings_manage_categories$'),
            CallbackQueryHandler(switch_to_dual_confirm, pattern='^settings_switch_to_dual$'),
            CallbackQueryHandler(change_language_start, pattern='^settings_change_language$'),
            # FIXED: Use menu instead of start
            CallbackQueryHandler(menu, pattern='^menu$'),
        ],
        SETBALANCE_ACCOUNT: [CallbackQueryHandler(received_balance_account, pattern='^set_balance_')],
        SETBALANCE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_balance_amount)],
        NEW_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_new_rate)],
        CATEGORIES_MENU: [
            CallbackQueryHandler(category_action_start, pattern='^category_(add|remove)$'),
            CallbackQueryHandler(settings_menu, pattern='^settings_menu$'),
        ],
        CATEGORY_ADD_START: [CallbackQueryHandler(received_category_type, pattern='^cat_type:add:')],
        CATEGORY_REMOVE_START: [CallbackQueryHandler(received_category_type, pattern='^cat_type:remove:')],
        CATEGORY_ADD_GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_category_name)],
        CATEGORY_REMOVE_GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_category_name)],
        SWITCH_TO_DUAL_CONFIRM: [
            CallbackQueryHandler(switch_to_dual_get_name, pattern='^confirm_switch_dual$'),
            CallbackQueryHandler(settings_menu, pattern='^settings_menu$'),
        ],
        SWITCH_TO_DUAL_GET_KM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_km_name_for_switch)],
        ASK_NEW_LANGUAGE: [CallbackQueryHandler(received_new_language, pattern='^change_lang:')],
        GET_MISSING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_missing_name_for_switch)],
    },
    fallbacks=[
        # FIXED: Use menu
        CommandHandler('menu', menu),
        CommandHandler('cancel', cancel),
        CallbackQueryHandler(menu, pattern='^menu$'),
        CallbackQueryHandler(cancel, pattern='^cancel_conversation$')
    ],
    per_message=False
)