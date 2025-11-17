from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import keyboards
import api_client
from decorators import authenticate_user
from .helpers import format_summation_results
from utils.i18n import t
from api_client import PremiumFeatureException

(
    CHOOSE_PERIOD, GET_CUSTOM_START, GET_CUSTOM_END, CHOOSE_TYPE,
    GET_CATEGORIES, GET_KEYWORDS, GET_KEYWORD_LOGIC, CHOOSE_ACTION
) = range(8)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")


@authenticate_user
async def search_menu_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        t("search.menu_header", context),
        reply_markup=keyboards.search_menu_keyboard(context)
    )
    return CHOOSE_ACTION


@authenticate_user
async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data['search_type'] = query.data.replace('start_search_', '')
    context.user_data['search_params'] = {}

    await query.edit_message_text(
        t("search.ask_period", context),
        reply_markup=keyboards.report_period_keyboard(context, is_search=True)
    )
    return CHOOSE_PERIOD


@authenticate_user
async def received_period_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    period = query.data.replace('report_period_', '')

    if period == 'custom':
        await query.edit_message_text(t("search.ask_start", context))
        return GET_CUSTOM_START

    if period != 'all_time':
        context.user_data['search_params']['period'] = period

    return await _ask_type(query.message, context)


@authenticate_user
async def received_custom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dt = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['search_params']['start_date'] = dt.isoformat()
        await update.message.reply_text(t("search.ask_end", context, date=dt))
        return GET_CUSTOM_END
    except ValueError:
        await update.message.reply_text(t("search.invalid_date", context))
        return GET_CUSTOM_START


@authenticate_user
async def received_custom_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        end = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        start_str = context.user_data['search_params'].get('start_date')

        if start_str and end < datetime.fromisoformat(start_str).date():
            await update.message.reply_text(t("search.invalid_range", context))
            return GET_CUSTOM_END

        context.user_data['search_params']['end_date'] = end.isoformat()
        return await _ask_type(update.message, context)
    except ValueError:
        await update.message.reply_text(t("search.invalid_date", context))
        return GET_CUSTOM_END


async def _ask_type(message, context):
    if message.from_user.is_bot:
        await message.edit_text(t("search.ask_type", context), reply_markup=keyboards.search_type_keyboard(context))
    else:
        await message.reply_text(t("search.ask_type", context), reply_markup=keyboards.search_type_keyboard(context))
    return CHOOSE_TYPE


@authenticate_user
async def received_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ttype = query.data.replace('search_type_', '')
    if ttype != 'all':
        context.user_data['search_params']['transaction_type'] = ttype

    await query.edit_message_text(t("search.ask_categories", context),
                                  reply_markup=keyboards.skip_keyboard(context, 'search_skip_categories'))
    return GET_CATEGORIES


@authenticate_user
async def received_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (update.callback_query and 'skip' in update.callback_query.data):
        cats = [c.strip() for c in update.message.text.split(',')]
        context.user_data['search_params']['categories'] = cats

    msg_text = t("search.ask_keywords", context)
    target = update.callback_query.message if update.callback_query else update.message

    if update.callback_query:
        await update.callback_query.answer()
        await target.edit_text(msg_text, reply_markup=keyboards.skip_keyboard(context, 'search_skip_keywords'))
    else:
        await target.reply_text(msg_text, reply_markup=keyboards.skip_keyboard(context, 'search_skip_keywords'))

    return GET_KEYWORDS


@authenticate_user
async def received_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query and 'skip' in update.callback_query.data:
        await update.callback_query.answer()
        return await _execute_search(update.callback_query.message, context)

    kws = [k.strip() for k in update.message.text.split(',')]
    context.user_data['search_params']['keywords'] = kws

    if len(kws) > 1:
        await update.message.reply_text(t("search.ask_logic", context),
                                        reply_markup=keyboards.search_keyword_logic_keyboard(context))
        return GET_KEYWORD_LOGIC

    context.user_data['search_params']['keyword_logic'] = 'OR'
    return await _execute_search(update.message, context)


@authenticate_user
async def received_keyword_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['search_params']['keyword_logic'] = query.data.replace('search_logic_', '').upper()
    return await _execute_search(query.message, context)


async def _execute_search(message, context):
    stype = context.user_data['search_type']
    params = context.user_data['search_params']
    jwt = context.user_data['jwt']

    loading = await message.edit_text(
        t("search.searching", context)) if message.from_user.is_bot else await message.reply_text(
        t("search.searching", context))

    try:
        if stype == 'manage':
            # Free tier allowed
            results = api_client.search_transactions_for_management(params, jwt)
            if not results:
                await loading.edit_text(t("search.no_results", context),
                                        reply_markup=keyboards.main_menu_keyboard(context))
            elif len(results) == 1:
                tx = results[0]
                emoji = "⬇️ Expense" if tx['type'] == 'expense' else "⬆️ Income"
                dt = datetime.fromisoformat(tx['timestamp']).astimezone(PHNOM_PENH_TZ).strftime('%d %b %Y, %I:%M %p')
                fmt = ",.0f" if tx['currency'] == 'KHR' else ",.2f"

                # Fix: Calculate string parts outside of nested f-string to avoid SyntaxError in Python 3.11
                amount_str = f"{tx['amount']:{fmt}}"
                desc_str = tx.get('description', 'N/A')

                details = t(
                    'history.tx_details_no_prompt',
                    context,
                    emoji=emoji,
                    amount=amount_str,
                    currency=tx['currency'],
                    category=tx['categoryId'],
                    description=desc_str,
                    date=dt
                )

                txt = f"{t('search.one_result', context)}\n\n{details}"
                await loading.edit_text(txt, parse_mode='HTML',
                                        reply_markup=keyboards.manage_tx_keyboard(tx['_id'], context))
            else:
                await loading.edit_text(t("search.many_results", context, count=len(results)),
                                        reply_markup=keyboards.history_keyboard(results, context, True))

        elif stype == 'sum':
            # Premium required
            results = api_client.sum_transactions_for_analytics(params, jwt)
            await loading.edit_text(format_summation_results(params, results, context), parse_mode='HTML',
                                    reply_markup=keyboards.main_menu_keyboard(context))

    except PremiumFeatureException:
        await loading.edit_text(t("common.premium_required", context),
                                reply_markup=keyboards.main_menu_keyboard(context))
    except Exception as e:
        await loading.edit_text(f"Error: {e}", reply_markup=keyboards.main_menu_keyboard(context))

    # Clear search params only
    context.user_data.pop('search_type', None)
    context.user_data.pop('search_params', None)

    return ConversationHandler.END