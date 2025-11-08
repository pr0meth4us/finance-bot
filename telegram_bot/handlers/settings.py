# --- Start of modified file: telegram_bot/handlers/settings.py ---

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

import api_client
import keyboards
from .common import start
from decorators import authenticate_user
from ..utils.i18n import t

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
    CATEGORY_REMOVE_GET_NAME
) = range(9)


@authenticate_user
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main settings menu."""
    query = update.callback_query
    await query.answer()

    user_id = context.user_data['user_profile']['_id']
    settings = api_client.get_user_settings(user_id)
    rate_data = api_client.get_exchange_rate(user_id)

    if not settings or not rate_data:
        await query.edit_message_text(
            t("common.error_generic", context, error="Could not load settings"),
            reply_markup=keyboards.main_menu_keyboard(context)
        )
        return ConversationHandler.END

    balances = settings.get('initial_balances', {})
    usd_bal = balances.get('USD', 0)
    khr_bal = balances.get('KHR', 0)
    rate_pref = settings.get('rate_preference', 'live')
    fixed_rate = settings.get('fixed_rate', 4100)
    current_rate = rate_data.get('rate', 4100)

    rate_text = (
        f"Fixed ({fixed_rate:,.0f})"
        if rate_pref == 'fixed'
        else f"Live ({current_rate:,.0f})"
    )

    text = t("settings.menu_header", context,
             usd_bal=usd_bal, khr_bal=khr_bal, rate_text=rate_text)

    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.settings_menu_keyboard(context)
    )
    return SETTINGS_MENU


# --- Set Balance Flow ---

async def set_balance_start(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    """Asks which account balance to set."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        t("settings.ask_balance_account", context),
        reply_markup=keyboards.set_balance_account_keyboard(context)
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

        if not currency:
            raise ValueError("Context lost")

        api_client.update_initial_balance(user_id, currency, amount)

        await update.message.reply_text(
            t("settings.balance_set_success", context,
              currency=currency, amount=amount)
        )
        return await start(update, context)

    except (ValueError, TypeError):
        await update.message.reply_text(
            t("tx.invalid_amount", context)
        )
        return SETBALANCE_AMOUNT
    except Exception as e:
        await update.message.reply_text(t("common.error_generic", context, error=e))
        return await start(update, context)


# --- Set Rate Flow ---

async def update_rate_start(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    """Asks for a new fixed exchange rate."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(t("settings.ask_rate", context))
    return NEW_RATE


async def received_new_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves the new fixed rate via the API."""
    try:
        user_id = context.user_data['user_profile']['_id']
        new_rate = float(update.message.text)

        api_client.update_exchange_rate(new_rate, user_id)

        await update.message.reply_text(
            t("settings.rate_set_success", context, rate=new_rate)
        )
        return await start(update, context)

    except (ValueError, TypeError):
        await update.message.reply_text(t("settings.invalid_rate", context))
        return NEW_RATE
    except Exception as e:
        await update.message.reply_text(t("common.error_generic", context, error=e))
        return await start(update, context)


# --- Manage Categories Flow ---

async def categories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the category management menu."""
    query = update.callback_query
    await query.answer()

    user_id = context.user_data['user_profile']['_id']
    settings = api_client.get_user_settings(user_id)
    if not settings:
        await query.edit_message_text(
            t("common.error_generic", context, error="Could not load categories"),
            reply_markup=keyboards.settings_menu_keyboard(context)
        )
        return SETTINGS_MENU

    categories = settings.get('categories', {})
    expense_cats = categories.get('expense', [])
    income_cats = categories.get('income', [])

    text = t("settings.categories_header", context,
             expense_cats=', '.join(expense_cats),
             income_cats=', '.join(income_cats))

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

        api_client.add_category(user_id, cat_type, cat_name)
        await update.message.reply_text(
            t("settings.category_add_success", context,
              name=cat_name, type=cat_type)
        )
        return await start(update, context)

    except Exception as e:
        await update.message.reply_text(t("common.error_generic", context, error=e))
        return await start(update, context)


async def received_category_remove_name(update: Update,
                                        context: ContextTypes.DEFAULT_TYPE):
    """Receives and removes the category name."""
    try:
        user_id = context.user_data['user_profile']['_id']
        cat_type = context.user_data['category_type']
        cat_name = update.message.text.strip().title()

        api_client.remove_category(user_id, cat_type, cat_name)
        await update.message.reply_text(
            t("settings.category_remove_success", context,
              name=cat_name, type=cat_type)
        )
        return await start(update, context)

    except Exception as e:
        await update.message.reply_text(t("common.error_generic", context, error=e))
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
    },
    fallbacks=[
        CommandHandler('start', start),
        CallbackQueryHandler(start, pattern='^start$')
    ],
    per_message=False
)

# --- End of modified file ---