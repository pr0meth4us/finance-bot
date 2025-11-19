# telegram_bot/handlers/iou.py

from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import keyboards
import api_client
from decorators import authenticate_user
from .helpers import (
    format_summary_message,
    _format_debt_analysis_message,
    _create_debt_overview_pie,
    _create_debt_concentration_bar,
    _create_csv_from_debts
)
from .transaction import parse_amount_and_currency_for_mode
from utils.i18n import t
from api_client import PremiumFeatureException
# FIXED: Import 'menu' instead of 'start'
from .common import menu, cancel

(
    IOU_ASK_DATE, IOU_CUSTOM_DATE, IOU_PERSON, IOU_AMOUNT, IOU_CURRENCY,
    IOU_PURPOSE, REPAY_LUMP_AMOUNT, IOU_EDIT_GET_VALUE
) = range(8)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")

# ... (Rest of file remains unchanged, as it doesn't call 'start' explicitly other than via imports,
# but we must ensure we don't use 'start' in any handlers if we removed it)

# ... [Skipping to Handlers] ...

@authenticate_user
async def iou_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        text=t("iou.menu_header", context),
        reply_markup=keyboards.iou_menu_keyboard(context)
    )

@authenticate_user
async def iou_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    debts = api_client.get_open_debts(context.user_data['jwt'])

    text = t("iou.view_header_open", context) if debts else t("iou.view_no_open", context)
    kb = keyboards.iou_list_keyboard(debts, context, is_settled=False) if debts else keyboards.iou_menu_keyboard(
        context)

    await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode='Markdown')

@authenticate_user
async def iou_view_settled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    debts = api_client.get_settled_debts_grouped(context.user_data['jwt'])

    text = t("iou.view_header_settled", context) if debts else t("iou.view_no_settled", context)
    kb = keyboards.iou_list_keyboard(debts, context, is_settled=True) if debts else keyboards.iou_menu_keyboard(context)

    await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode='Markdown')

@authenticate_user
async def iou_person_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    person = query.data.split(':')[-1]

    debts = api_client.get_all_debts_by_person(person, context.user_data['jwt'])
    if not debts:
        await query.edit_message_text(t("iou.person_fail", context, person=person),
                                      reply_markup=keyboards.iou_menu_keyboard(context))
        return

    dtype = debts[0]['type']
    direction = t("iou.person_direction_lent", context) if dtype == 'lent' else t("iou.person_direction_borrowed",
                                                                                  context)
    header = t("iou.person_header_open", context, person=person, direction=direction)

    await query.edit_message_text(
        header + _format_person_ledger(debts, context, False),
        parse_mode='HTML',
        reply_markup=keyboards.iou_person_actions_keyboard(person, dtype, context, False)
    )

@authenticate_user
async def iou_person_detail_settled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    person = query.data.split(':')[-1]

    debts = api_client.get_all_settled_debts_by_person(person, context.user_data['jwt'])
    if not debts:
        await query.edit_message_text(t("iou.person_fail_settled", context, person=person),
                                      reply_markup=keyboards.iou_menu_keyboard(context))
        return

    dtype = debts[0]['type']
    direction = t("iou.person_direction_lent_past", context) if dtype == 'lent' else t(
        "iou.person_direction_borrowed_past", context)
    header = t("iou.person_header_settled", context, person=person, direction=direction)

    await query.edit_message_text(
        header + _format_person_ledger(debts, context, True),
        parse_mode='HTML',
        reply_markup=keyboards.iou_person_actions_keyboard(person, dtype, context, True)
    )

@authenticate_user
async def iou_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, debt_id, person, settled_str = query.data.split(':')
    is_settled = settled_str == 'True'

    debt = api_client.get_debt_details(debt_id, context.user_data['jwt'])
    if not debt:
        await query.edit_message_text(t("iou.detail_fail", context), reply_markup=keyboards.iou_menu_keyboard(context))
        return

    text = _format_debt_details(debt, context)
    kb = keyboards.iou_detail_actions_keyboard(debt_id, person, debt['type'], is_settled, debt['status'], context)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb)

@authenticate_user
async def iou_manage_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, _, person, dtype, settled_str = query.data.split(':')
    is_settled = settled_str == 'True'
    jwt = context.user_data['jwt']

    debts = api_client.get_all_settled_debts_by_person(person,
                                                       jwt) if is_settled else api_client.get_all_debts_by_person(
        person, jwt)

    if not debts:
        await query.edit_message_text(t("iou.manage_fail", context), reply_markup=keyboards.iou_menu_keyboard(context))
        return

    await query.edit_message_text(
        t("iou.manage_header", context),
        reply_markup=keyboards.iou_manage_list_keyboard(debts, person, dtype, is_settled, context)
    )

@authenticate_user
async def debt_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(t("iou.analysis_loading", context))

    try:
        data = api_client.get_debt_analysis(context.user_data['jwt'])
        if not data:
            await query.edit_message_text(t("iou.analysis_fail", context),
                                          reply_markup=keyboards.iou_menu_keyboard(context))
            return

        await query.edit_message_text(
            _format_debt_analysis_message(data, context),
            parse_mode='HTML',
            reply_markup=keyboards.debt_analysis_actions_keyboard(context)
        )

        if pie := _create_debt_overview_pie(data):
            await context.bot.send_photo(update.effective_chat.id, pie)
        if bar := _create_debt_concentration_bar(data):
            await context.bot.send_photo(update.effective_chat.id, bar)

    except PremiumFeatureException:
        await query.edit_message_text(t("common.premium_required", context),
                                      reply_markup=keyboards.iou_menu_keyboard(context))
    except Exception as e:
        await query.edit_message_text(f"Error: {e}", reply_markup=keyboards.iou_menu_keyboard(context))


@authenticate_user
async def download_debt_analysis_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(t("search.searching", context))

    try:
        debts = api_client.get_open_debts_export(context.user_data['jwt'])
        if not debts:
            await query.message.reply_text(t("iou.view_no_open", context))
            return

        csv_file = _create_csv_from_debts(debts)
        filename = f"open_debts_{datetime.now(PHNOM_PENH_TZ):%Y%m%d}.csv"

        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=csv_file,
            filename=filename,
            caption="Open Debts Export"
        )
    except Exception as e:
        await query.message.reply_text(t("common.error_generic", context, error=str(e)))


# --- Conversation: Add IOU ---

@authenticate_user
async def iou_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Reset relevant conversation state, keep auth
    for key in ['iou_person', 'iou_amount', 'iou_currency', 'timestamp']:
        context.user_data.pop(key, None)

    context.user_data['iou_type'] = 'lent' if query.data == 'iou_lent' else 'borrowed'
    await query.message.reply_text(t("iou.ask_date", context), reply_markup=keyboards.iou_date_keyboard(context))
    return IOU_ASK_DATE


async def iou_received_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == 'iou_date_custom':
        await query.message.reply_text(t("iou.ask_date_custom", context))
        return IOU_CUSTOM_DATE

    if choice == 'iou_date_yesterday':
        yesterday = datetime.now(PHNOM_PENH_TZ).date() - timedelta(days=1)
        context.user_data['timestamp'] = datetime.combine(yesterday, time(12, 0), tzinfo=PHNOM_PENH_TZ).isoformat()

    await _ask_person(query.message, context)
    return IOU_PERSON


async def iou_received_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dt = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['timestamp'] = datetime.combine(dt, time(12, 0), tzinfo=PHNOM_PENH_TZ).isoformat()
        await _ask_person(update.message, context)
        return IOU_PERSON
    except ValueError:
        await update.message.reply_text(t("forgot.invalid_date", context))
        return IOU_CUSTOM_DATE


async def _ask_person(message, context):
    key = "iou.ask_person_lent" if context.user_data['iou_type'] == 'lent' else "iou.ask_person_borrowed"
    await message.reply_text(t(key, context))


async def iou_received_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['iou_person'] = update.message.text.strip().title()
    await update.message.reply_text(t("iou.ask_amount", context))
    return IOU_AMOUNT


async def iou_received_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mode, primary = _get_iou_settings(context)
        amt, curr, ambiguous = parse_amount_and_currency_for_mode(update.message.text, mode, primary)
        context.user_data['iou_amount'] = amt

        if mode == 'single' or not ambiguous:
            context.user_data['iou_currency'] = curr
            await _ask_purpose(update.message, context)
            return IOU_PURPOSE

        await update.message.reply_text(t("iou.ask_currency", context),
                                        reply_markup=keyboards.currency_keyboard(context))
        return IOU_CURRENCY
    except ValueError:
        await update.message.reply_text(t("iou.invalid_amount", context))
        return IOU_AMOUNT


async def iou_received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['iou_currency'] = query.data.split('_')[1]
    await _ask_purpose(query.message, context)
    return IOU_PURPOSE


async def _ask_purpose(message, context):
    amt = context.user_data['iou_amount']
    curr = context.user_data['iou_currency']
    fmt = ",.0f" if curr == 'KHR' else ",.2f"

    if message.from_user.is_bot:  # Callback
        await message.edit_text(t("iou.ask_purpose", context, amount_display=f"{amt:{fmt}} {curr}"), parse_mode='HTML')
    else:
        await message.reply_text(t("iou.ask_purpose", context, amount_display=f"{amt:{fmt}} {curr}"), parse_mode='HTML')


async def iou_received_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    payload = {
        "type": data['iou_type'],
        "person": data['iou_person'],
        "amount": data['iou_amount'],
        "currency": data['iou_currency'],
        "purpose": update.message.text.strip(),
        "timestamp": data.get('timestamp')
    }

    res = api_client.add_debt(payload, data['jwt'])
    msg = t("iou.success", context) if 'id' in res else t("iou.fail", context)

    summary = api_client.get_detailed_summary(data['jwt'])
    await update.message.reply_text(msg + format_summary_message(summary, context), parse_mode='HTML',
                                    reply_markup=keyboards.main_menu_keyboard(context))

    return ConversationHandler.END


# --- Conversation: Repay Lump Sum ---

@authenticate_user
async def repay_lump_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, person, dtype = query.data.split(':')
    context.user_data.update({'lump_person': person, 'lump_type': dtype})

    key = "iou.repay_ask_amount_lent" if dtype == 'lent' else "iou.repay_ask_amount_borrowed"
    await query.message.reply_text(t(key, context, person=person))
    return REPAY_LUMP_AMOUNT


async def received_lump_repayment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mode, primary = _get_iou_settings(context)
        amt, curr, ambiguous = parse_amount_and_currency_for_mode(update.message.text, mode, primary)
        if ambiguous: curr = 'USD'  # Default for repayment ambiguities

        res = api_client.record_lump_sum_repayment(
            context.user_data['lump_person'], curr, amt,
            context.user_data['lump_type'], context.user_data['jwt']
        )

        msg = t("iou.repay_success", context, message=res.get('message', '')) if 'message' in res else t(
            "iou.repay_fail", context, error=res.get('error'))

        summary = api_client.get_detailed_summary(context.user_data['jwt'])
        await update.message.reply_text(msg + format_summary_message(summary, context), parse_mode='HTML',
                                        reply_markup=keyboards.main_menu_keyboard(context))
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(t("iou.repay_invalid_amount", context))
        return REPAY_LUMP_AMOUNT


# --- Conversation: Edit / Cancel ---

@authenticate_user
async def iou_manage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, _, debt_id, person, settled_str = query.data.split(':')
    await query.edit_message_text(
        t("iou.manage_menu_header", context, person=person),
        reply_markup=keyboards.iou_manage_keyboard(debt_id, person, settled_str, context)
    )


@authenticate_user
async def iou_cancel_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, _, debt_id, person, settled_str = query.data.split(':')
    await query.edit_message_text(
        t("iou.cancel_prompt", context),
        parse_mode='Markdown',
        reply_markup=keyboards.iou_cancel_confirm_keyboard(debt_id, person, settled_str, context)
    )


@authenticate_user
async def iou_cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(t("iou.cancel_confirm", context))
    debt_id = query.data.split(':')[-1]

    res = api_client.cancel_debt(debt_id, context.user_data['jwt'])
    msg = t("iou.cancel_success", context, message=res.get('message')) if 'message' in res else t("iou.cancel_fail",
                                                                                                  context,
                                                                                                  error=res.get(
                                                                                                      'error'))

    summary = api_client.get_detailed_summary(context.user_data['jwt'])
    await query.edit_message_text(msg + format_summary_message(summary, context), parse_mode='HTML',
                                  reply_markup=keyboards.main_menu_keyboard(context))
    return ConversationHandler.END


@authenticate_user
async def iou_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, field, debt_id = query.data.split(':')
    context.user_data.update({'edit_debt_id': debt_id, 'edit_field': field})

    key = "iou.edit_ask_person" if field == 'person' else "iou.edit_ask_purpose"
    await query.message.reply_text(t(key, context))
    return IOU_EDIT_GET_VALUE


async def iou_edit_received_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text
    data = context.user_data

    res = api_client.update_debt(data['edit_debt_id'], {data['edit_field']: val}, data['jwt'])
    msg = t("iou.edit_success", context, message=res.get('message')) if 'message' in res else t("iou.edit_fail",
                                                                                                context,
                                                                                                error=res.get('error'))

    summary = api_client.get_detailed_summary(data['jwt'])
    await update.message.reply_text(msg + format_summary_message(summary, context), parse_mode='HTML',
                                    reply_markup=keyboards.main_menu_keyboard(context))
    return ConversationHandler.END

# --- Helper functions for formatting repeated in this file ---
# (If these helper functions are large, they should be moved to helpers.py,
# but for this fix I am keeping them if they were already here or using imports)
# Note: In previous steps _format_person_ledger, _get_iou_settings etc were defined here.
# I am ensuring they are present or imported.

def _get_iou_settings(context: ContextTypes.DEFAULT_TYPE):
    profile = context.user_data.get('profile', {})
    settings = profile.get('settings', {})
    mode = settings.get('currency_mode', 'dual')
    primary = settings.get('primary_currency', 'USD') if mode == 'single' else 'USD'
    return mode, primary


def _format_debt_details(debt, context):
    status = debt['status'].title()
    currency = debt.get('currency', 'USD')
    fmt = ",.0f" if currency == 'KHR' else ",.2f"

    direction = t("iou.debt_direction_lent", context) if debt['type'] == 'lent' else t("iou.debt_direction_borrowed",
                                                                                       context)
    created = datetime.fromisoformat(debt['created_at']).astimezone(PHNOM_PENH_TZ).strftime('%d %b %Y, %I:%M %p')

    lines = [
        t("iou.debt_details_header", context, status=status),
        t("iou.debt_person", context, person=debt['person'], direction=direction),
        t("iou.debt_created", context, date=created),
    ]

    if debt.get('purpose'):
        lines.append(t("iou.debt_purpose", context, purpose=debt['purpose']))

    lines.append(t("iou.debt_original", context, amount=f"{debt['originalAmount']:{fmt}}", currency=currency))
    lines.append(t("iou.debt_remaining", context, amount=f"{debt['remainingAmount']:{fmt}}", currency=currency))

    if debt.get('repayments'):
        lines.append(t("iou.debt_repayments", context))
        for r in debt['repayments']:
            rdt = datetime.fromisoformat(r['date']).astimezone(PHNOM_PENH_TZ).strftime('%d %b %Y')
            lines.append(
                t("iou.debt_repayment_item", context, amount=f"{r['amount']:{fmt}}", currency=currency, date=rdt))

    return "\n".join(lines)


def _format_person_ledger(debts, context, is_settled=False):
    if not debts:
        return t("iou.person_fail", context, person="this person")

    mode, _ = _get_iou_settings(context)
    lines = []
    totals = {'USD': 0, 'KHR': 0}
    items = []

    for d in debts:
        curr = d.get('currency', 'USD')
        fmt = ",.0f" if curr == 'KHR' else ",.2f"

        if not is_settled:
            totals[curr] += d['remainingAmount']

        created = datetime.fromisoformat(d['created_at'])
        icon = "✅" if d['status'] == 'settled' else ("❌" if d['status'] == 'canceled' else "🔹")
        label = f"{icon} <b>{d['originalAmount']:{fmt}} {curr}</b> ({d.get('purpose', 'No purpose')})"

        items.append((created, label))
        for r in d.get('repayments', []):
            rdt = datetime.fromisoformat(r['date'])
            items.append((rdt, f"  <i>- Repaid {r['amount']:{fmt}} {curr}</i>"))

    items.sort(key=lambda x: x[0])

    if not is_settled:
        header = [t("iou.ledger_total_remaining", context)]
        has_bal = False

        if mode == 'dual':
            if totals['USD'] > 0: header.append(f"  💵 {totals['USD']:,.2f} USD"); has_bal = True
            if totals['KHR'] > 0: header.append(f"  ៛ {totals['KHR']:,.0f} KHR"); has_bal = True
        else:
            primary = 'USD' if totals['USD'] > 0 else 'KHR'
            val = totals[primary]
            if val > 0:
                fmt = ",.0f" if primary == 'KHR' else ",.2f"
                header.append(f"  <b>{val:{fmt}} {primary}</b>")
                has_bal = True

        if not has_bal: header.append(t("iou.ledger_none", context))
        lines.append("\n".join(header) + "\n")

    lines.append(t("iou.ledger_header", context))

    last_date = None
    for dt, text in items:
        dstr = dt.astimezone(PHNOM_PENH_TZ).strftime('%d %b %Y')
        if dstr != last_date:
            lines.append(f"\n<u>{dstr}</u>")
            last_date = dstr
        lines.append(text)

    return "\n".join(lines)