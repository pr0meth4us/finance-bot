# --- Start of modified file: telegram_bot/handlers/settings.py ---

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    CommandHandler
)
import logging  # Import logging
import api_client
import keyboards
from .common import start, cancel  # <-- THIS IS THE FIX
from decorators import authenticate_user
from utils.i18n import t

log = logging.getLogger(__name__) # Add logger

# Conversation states
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
    SWITCH_TO_DUAL_GET_KM_NAME
) = range(11)


def _get_user_settings_for_settings(context: ContextTypes.DEFAULT_TYPE):
    """Helper to safely get user settings and currency mode."""
    profile = context.user_data.get('user_profile', {})
    settings = profile.get('settings', {})
    mode = settings.get('currency_mode', 'dual')

    if mode == 'single':
        primary_currency = settings.get('primary_currency', 'USD')
        return mode, (primary_currency,)

    return 'dual', ('USD', 'KHR')


@authenticate_user
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main settings menu."""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = context.user_data['user_profile']['_id']
    log.info(f"User {user_id} entering settings menu.")

    # Use the /settings/ endpoint which returns settings + names
    user_data = api_client.get_user_settings(user_id)
    rate_data = api_client.get_exchange_rate(user_id)

    if not user_data or not rate_data:
        err_msg = t("common.error_generic", context)
        if query:
            await query.edit_message_text(
                err_msg,
                reply_markup=keyboards.main_menu_keyboard(context)
            )
        else:
            await update.message.reply_text(
                err_msg,
                reply_markup=keyboards.main_menu_keyboard(context)
            )
        return ConversationHandler.END

    # Update local cache with fresh data
    context.user_data['user_profile']['settings'] = user_data.get('settings', {})
    context.user_data['user_profile']['name_en'] = user_data.get('name_en')
    context.user_data['user_profile']['name_km'] = user_data.get('name_km')

    settings = user_data.get('settings', {})
    balances = settings.get('initial_balances', {})
    rate_pref = settings.get('rate_preference', 'live')
    fixed_rate = settings.get('fixed_rate', 4100)
    current_rate = rate_data.get('rate', 4100)

    mode, currencies = _get_user_settings_for_settings(context)

    balance_lines = []
    if mode == 'dual':
        usd_bal = balances.get('USD', 0)
        khr_bal = balances.get('KHR', 0)
        balance_lines.append(f"  💵 ${usd_bal:,.2f} USD")
        balance_lines.append(f"  ៛ {khr_bal:,.0f} KHR")
    else:
        curr = currencies[0]
        bal = balances.get(curr, 0)
        fmt = ",.0f" if curr == 'KHR' else ",.2f"
        balance_lines.append(f"  <b>{bal:{fmt}} {curr}</b>")

    balance_text = "\n".join(balance_lines)

    rate_text = (
        f"Fixed ({fixed_rate:,.0f})"
        if rate_pref == 'fixed'
        else f"Live ({current_rate:,.0f})"
    )

    text = t("settings.menu_header", context,
             balance_text=balance_text,
             rate_text=rate_text,
             mode=mode.title()
             )

    keyboard = keyboards.settings_menu_keyboard(context)

    if query:
        await query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            text=text,
            parse_mode='HTML',
            reply_markup=keyboard
        )

    return SETTINGS_MENU


# --- Set Balance Flow ---

async def set_balance_start(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    """Asks which account balance to set."""
    query = update.callback_query
    await query.answer()
    log.info(f"User {context.user_data['user_profile']['_id']} starting set_balance flow.")

    mode, currencies = _get_user_settings_for_settings(context)

    await query.edit_message_text(
        t("settings.ask_balance_account", context),
        reply_markup=keyboards.set_balance_account_keyboard(context, mode, currencies)
    )
    return SETBALANCE_ACCOUNT


async def received_balance_account(update: Update,
                                   context: ContextTypes.DEFAULT_TYPE):
    """Asks for the new amount for the selected account."""
    query = update.callback_query
    await query.answer()
    currency = query.data.split('_')[-1]
    context.user_data['settings_currency'] = currency
    await query.edit_message_text(
        t("settings.ask_balance_amount", context, currency=currency),
        parse_mode='HTML'
    )
    return SETBALANCE_AMOUNT


async def received_balance_amount(update: Update,
                                  context: ContextTypes.DEFAULT_TYPE):
    """Saves the new initial balance to the API."""
    try:
        user_id = context.user_data['user_profile']['_id']
        amount = float(update.message.text)
        currency = context.user_data.get('settings_currency')
        log.info(f"User {user_id} setting balance for {currency} to {amount}.")

        if not currency:
            log.warning(f"User {user_id} lost context in received_balance_amount.")
            raise ValueError("Context lost")

        api_client.update_initial_balance(user_id, currency, amount)

        await update.message.reply_text(
            t("settings.balance_set_success", context,
              currency=currency, amount=amount)
        )

        # Go back to settings menu
        return await settings_menu(update, context)

    except (ValueError, TypeError):
        await update.message.reply_text(
            t("tx.invalid_amount", context)
        )
        return SETBALANCE_AMOUNT
    except Exception as e:
        log.error(f"Error in received_balance_amount: {e}", exc_info=True)
        await update.message.reply_text(t("common.error_generic", context))
        return await start(update, context)


# --- Set Rate Flow ---

async def update_rate_start(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    """Asks for a new fixed exchange rate."""
    query = update.callback_query
    await query.answer()
    log.info(f"User {context.user_data['user_profile']['_id']} starting update_rate flow.")
    await query.edit_message_text(t("settings.ask_rate", context))
    return NEW_RATE


async def received_new_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves the new fixed rate via the API."""
    try:
        user_id = context.user_data['user_profile']['_id']
        new_rate = float(update.message.text)
        log.info(f"User {user_id} setting new fixed rate to {new_rate}.")

        api_client.update_exchange_rate(new_rate, user_id)

        await update.message.reply_text(
            t("settings.rate_set_success", context, rate=new_rate)
        )
        return await settings_menu(update, context)

    except (ValueError, TypeError):
        await update.message.reply_text(t("settings.invalid_rate", context))
        return NEW_RATE
    except Exception as e:
        log.error(f"Error in received_new_rate: {e}", exc_info=True)
        await update.message.reply_text(t("common.error_generic", context))
        return await start(update, context)


# --- Manage Categories Flow ---

async def categories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the category management menu."""
    query = update.callback_query
    await query.answer()
    user_id = context.user_data['user_profile']['_id']
    log.info(f"User {user_id} entering categories menu.")

    user_data = api_client.get_user_settings(user_id)
    if not user_data:
        await query.edit_message_text(
            t("common.error_generic", context),
            reply_markup=keyboards.settings_menu_keyboard(context)
        )
        return SETTINGS_MENU

    categories = user_data.get('settings', {}).get('categories', {})
    expense_cats = categories.get('expense', [])
    income_cats = categories.get('income', [])

    text = t("settings.categories_header", context,
             expense_cats=', '.join(expense_cats) or 'None',
             income_cats=', '.join(income_cats) or 'None')

    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.manage_categories_keyboard(context)
    )
    return CATEGORIES_MENU


async def category_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks for the type of category to add."""
    query = update.callback_query
    await query.answer()
    context.user_data['category_action'] = 'add'
    await query.edit_message_text(
        t("settings.category_ask_add", context),
        reply_markup=keyboards.category_type_keyboard(context, 'add')
    )
    return CATEGORY_ADD_START


async def category_remove_start(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    """Asks for the type of category to remove."""
    query = update.callback_query
    await query.answer()
    context.user_data['category_action'] = 'remove'
    await query.edit_message_text(
        t("settings.category_ask_remove", context),
        reply_markup=keyboards.category_type_keyboard(context, 'remove')
    )
    return CATEGORY_REMOVE_START


async def received_category_type(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    """Receives category type and asks for the name."""
    query = update.callback_query
    await query.answer()

    action = context.user_data['category_action']
    cat_type = query.data.split(':')[-1]
    context.user_data['category_type'] = cat_type

    await query.edit_message_text(
        t("settings.category_ask_name", context,
          cat_type=cat_type, action=action)
    )
    if action == 'add':
        return CATEGORY_ADD_GET_NAME
    if action == 'remove':
        return CATEGORY_REMOVE_GET_NAME
    return SETTINGS_MENU


async def received_category_add_name(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
    """Receives and saves the new category name."""
    try:
        user_id = context.user_data['user_profile']['_id']
        cat_type = context.user_data['category_type']
        cat_name = update.message.text.strip().title()
        log.info(f"User {user_id} adding category '{cat_name}' to {cat_type}.")

        api_client.add_category(user_id, cat_type, cat_name)
        await update.message.reply_text(
            t("settings.category_add_success", context,
              name=cat_name, type=cat_type)
        )
        return await settings_menu(update, context)

    except Exception as e:
        log.error(f"Error in received_category_add_name: {e}", exc_info=True)
        await update.message.reply_text(t("common.error_generic", context))
        return await start(update, context)


async def received_category_remove_name(update: Update,
                                        context: ContextTypes.DEFAULT_TYPE):
    """Receives and removes the category name."""
    try:
        user_id = context.user_data['user_profile']['_id']
        cat_type = context.user_data['category_type']
        cat_name = update.message.text.strip().title()
        log.info(f"User {user_id} removing category '{cat_name}' from {cat_type}.")

        api_client.remove_category(user_id, cat_type, cat_name)
        await update.message.reply_text(
            t("settings.category_remove_success", context,
              name=cat_name, type=cat_type)
        )
        return await settings_menu(update, context)

    except Exception as e:
        log.error(f"Error in received_category_remove_name: {e}", exc_info=True)
        await update.message.reply_text(t("common.error_generic", context))
        return await start(update, context)


# --- Switch Mode Flow ---

async def switch_to_dual_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks the user to confirm switching to dual-currency mode."""
    query = update.callback_query
    await query.answer()
    log.info(f"User {context.user_data['user_profile']['_id']} starting switch_to_dual flow.")

    await query.edit_message_text(
        t("settings.switch_to_dual_confirm", context),
        reply_markup=keyboards.switch_to_dual_confirm_keyboard(context)
    )
    return SWITCH_TO_DUAL_CONFIRM


async def switch_to_dual_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks for the user's Khmer name."""
    query = update.callback_query
    await query.answer()

    # Set language to Khmer by default for this prompt
    context.user_data['user_profile']['settings']['language'] = 'km'

    await query.edit_message_text(
        t("settings.ask_name_km_switch", context)
    )
    return SWITCH_TO_DUAL_GET_KM_NAME


async def received_km_name_for_switch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the Khmer name and finalizes the mode switch."""
    try:
        km_name = update.message.text.strip()
        user_id = context.user_data['user_profile']['_id']
        log.info(f"User {user_id} completing switch_to_dual with KM name.")

        # Get existing English name
        name_en = context.user_data['user_profile'].get('name_en', 'User')

        # Use the /settings/mode endpoint to update
        api_client.update_user_mode(
            user_id,
            mode='dual',
            language='km', # Default to Khmer upon switch
            name_en=name_en,
            name_km=km_name
        )

        # Update local cache
        context.user_data['user_profile']['settings']['currency_mode'] = 'dual'
        context.user_data['user_profile']['settings']['language'] = 'km'
        context.user_data['user_profile']['name_km'] = km_name

        await update.message.reply_text(
            t("settings.switch_to_dual_success", context)
        )
        return await settings_menu(update, context)

    except Exception as e:
        log.error(f"Error in received_km_name_for_switch: {e}", exc_info=True)
        await update.message.reply_text(t("common.error_generic", context))
        return await start(update, context)


settings_conversation_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(settings_menu, pattern='^settings_menu$')
    ],
    states={
        SETTINGS_MENU: [
            CallbackQueryHandler(
                set_balance_start, pattern='^settings_set_balance$'
            ),
            CallbackQueryHandler(
                update_rate_start, pattern='^settings_set_rate$'
            ),
            CallbackQueryHandler(
                categories_menu, pattern='^settings_manage_categories$'
            ),
            CallbackQueryHandler(
                switch_to_dual_confirm, pattern='^settings_switch_to_dual$'
            ),
            CallbackQueryHandler(start, pattern='^start$'),
        ],
        SETBALANCE_ACCOUNT: [
            CallbackQueryHandler(
                received_balance_account, pattern='^set_balance_'
            )
        ],
        SETBALANCE_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND,
                           received_balance_amount)
        ],
        NEW_RATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, received_new_rate)
        ],
        CATEGORIES_MENU: [
            CallbackQueryHandler(
                category_add_start, pattern='^category_add$'
            ),
            CallbackQueryHandler(
                category_remove_start, pattern='^category_remove$'
            ),
            CallbackQueryHandler(settings_menu, pattern='^settings_menu$'),
        ],
        CATEGORY_ADD_START: [
            CallbackQueryHandler(
                received_category_type, pattern='^cat_type:add:'
            )
        ],
        CATEGORY_REMOVE_START: [
            CallbackQueryHandler(
                received_category_type, pattern='^cat_type:remove:'
            )
        ],
        CATEGORY_ADD_GET_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND,
                           received_category_add_name)
        ],
        CATEGORY_REMOVE_GET_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND,
                           received_category_remove_name)
        ],
        SWITCH_TO_DUAL_CONFIRM: [
            CallbackQueryHandler(
                switch_to_dual_get_name, pattern='^confirm_switch_dual$'
            ),
            CallbackQueryHandler(settings_menu, pattern='^settings_menu$'),
        ],
        SWITCH_TO_DUAL_GET_KM_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND,
                           received_km_name_for_switch)
        ],
    },
    fallbacks=[
        CommandHandler('start', start),
        CommandHandler('cancel', cancel),
        CallbackQueryHandler(start, pattern='^start$'),
        CallbackQueryHandler(cancel, pattern='^cancel_conversation$')
    ],
    per_message=False
)

# --- End of modified file ---