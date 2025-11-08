# --- Start of file: telegram_bot/handlers/iou.py ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import keyboards
import api_client
from decorators import authenticate_user # <-- MODIFIED: Import new decorator
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from .helpers import (
    format_summary_message,
    _format_debt_analysis_message,
    _create_debt_overview_pie,
    _create_debt_concentration_bar
)
from .command_handler import parse_amount_and_currency
from utils.i18n import t

# Conversation states
(
    IOU_ASK_DATE, IOU_CUSTOM_DATE, IOU_PERSON, IOU_AMOUNT, IOU_CURRENCY, IOU_PURPOSE,
    REPAY_LUMP_AMOUNT,
    IOU_EDIT_GET_VALUE
) = range(8)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")

def _format_debt_details(debt, context: ContextTypes.DEFAULT_TYPE):
    """Helper to format the full details of a debt, including repayments."""
    direction = t("iou.debt_direction_lent", context) if debt['type'] == 'lent' else t("iou.debt_direction_borrowed", context)
    purpose_text = t("iou.debt_purpose", context, purpose=debt['purpose']) if debt.get('purpose') else ""
    created_date = datetime.fromisoformat(debt['created_at'].replace('Z', '+00:00')).astimezone(PHNOM_PENH_TZ).strftime(
        '%d %b %Y, %I:%M %p')
    amount_format = ",.0f" if debt['currency'] == 'KHR' else ",.2f"

    text_lines = [
        t("iou.debt_details_header", context, status=debt['status'].title()),
        t("iou.debt_person", context, person=debt['person'], direction=direction),
        t("iou.debt_created", context, date=created_date),
        purpose_text,
        t("iou.debt_original", context, amount=f"{debt['originalAmount']:{amount_format}}", currency=debt['currency']),
        t("iou.debt_remaining", context, amount=f"{debt['remainingAmount']:{amount_format}}", currency=debt['currency'])
    ]

    repayments = debt.get('repayments', [])
    if repayments:
        text_lines.append(t("iou.debt_repayments", context))
        for rep in repayments:
            rep_date = datetime.fromisoformat(rep['date'].replace('Z', '+00:00')).astimezone(PHNOM_PENH_TZ).strftime('%d %b %Y')
            text_lines.append(t("iou.debt_repayment_item", context, amount=f"{rep['amount']:{amount_format}}", currency=debt['currency'], date=rep_date))

    return "\n".join(text_lines)


def _format_person_ledger(person_debts, context: ContextTypes.DEFAULT_TYPE, is_settled=False):
    """Formats all debts and repayments for one person into a single chronological list."""

    if not person_debts:
        return t("iou.person_fail", context, person="this person") # Fallback text

    ledger_items = [] # (datetime_obj, text_string, currency)
    total_remaining_usd = 0
    total_remaining_khr = 0

    for debt in person_debts:
        created_dt = datetime.fromisoformat(debt['created_at'].replace('Z', '+00:00'))
        amount_format = ",.0f" if debt['currency'] == 'KHR' else ",.2f"

        if debt['currency'] == 'USD':
            total_remaining_usd += debt['remainingAmount']
        else:
            total_remaining_khr += debt['remainingAmount']

        purpose = debt.get('purpose') or "No purpose"
        amount = debt['originalAmount']
        status_icon = "✅" if debt['status'] == 'settled' else ("❌" if debt['status'] == 'canceled' else "🔹")

        debt_text = f"{status_icon} <b>{amount:{amount_format}} {debt['currency']}</b> ({purpose})"
        ledger_items.append((created_dt, debt_text, debt['currency']))

        for rep in debt.get('repayments', []):
            rep_dt = datetime.fromisoformat(rep['date'].replace('Z', '+00:00'))
            rep_text = f"  <i>- Repaid {rep['amount']:{amount_format}} {debt['currency']}</i>"
            ledger_items.append((rep_dt, rep_text, debt['currency']))

    ledger_items.sort(key=lambda x: x[0])

    date_format = '%d %b %Y'
    last_date = None
    ledger_lines = []

    if not is_settled:
        header_lines = [t("iou.ledger_total_remaining", context)]
        if total_remaining_usd > 0:
            header_lines.append(f"  💵 {total_remaining_usd:,.2f} USD")
        if total_remaining_khr > 0:
            header_lines.append(f"  ៛ {total_remaining_khr:,.0f} KHR")
        if total_remaining_usd == 0 and total_remaining_khr == 0:
            header_lines.append(t("iou.ledger_none", context))
        ledger_lines.append("\n".join(header_lines) + "\n")

    ledger_lines.append(t("iou.ledger_header", context))

    for item_dt, item_text, item_currency in ledger_items:
        current_date_str = item_dt.astimezone(PHNOM_PENH_TZ).strftime(date_format)
        if current_date_str != last_date:
            ledger_lines.append(f"\n<u>{current_date_str}</u>")
            last_date = current_date_str
        ledger_lines.append(item_text)

    return "\n".join(ledger_lines)


# --- IOU Menu & Standalone Handlers ---
@authenticate_user # <-- MODIFIED
async def iou_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the IOU management menu."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=t("iou.menu_header", context),
        reply_markup=keyboards.iou_menu_keyboard(context)
    )


@authenticate_user # <-- MODIFIED
async def iou_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a summary list of all open debts, grouped by person."""
    query = update.callback_query
    await query.answer()

    # --- MODIFICATION: Get user_id and pass to API ---
    user_id = context.user_data['user_profile']['_id']
    grouped_debts = api_client.get_open_debts(user_id)
    # ---

    text = t("iou.view_header_open", context)
    keyboard = keyboards.iou_list_keyboard(grouped_debts, context, is_settled=False)
    if not grouped_debts:
        text = t("iou.view_no_open", context)
        keyboard = keyboards.iou_menu_keyboard(context)
    await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode='Markdown')


@authenticate_user # <-- MODIFIED
async def iou_view_settled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a summary list of all settled debts, grouped by person."""
    query = update.callback_query
    await query.answer()

    # --- MODIFICATION: Get user_id and pass to API ---
    user_id = context.user_data['user_profile']['_id']
    grouped_debts = api_client.get_settled_debts_grouped(user_id)
    # ---

    text = t("iou.view_header_settled", context)
    keyboard = keyboards.iou_list_keyboard(grouped_debts, context, is_settled=True)
    if not grouped_debts:
        text = t("iou.view_no_settled", context)
        keyboard = keyboards.iou_menu_keyboard(context)
    await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode='Markdown')


@authenticate_user # <-- MODIFIED
async def iou_person_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a unified ledger of all open debts for a specific person."""
    query = update.callback_query
    await query.answer()
    _, _, _, person_name = query.data.split(':')

    # --- MODIFICATION: Get user_id and pass to API ---
    user_id = context.user_data['user_profile']['_id']
    person_debts = api_client.get_all_debts_by_person(person_name, user_id)
    # ---

    if not person_debts:
        await query.edit_message_text(
            t("iou.person_fail", context, person=person_name),
            reply_markup=keyboards.iou_menu_keyboard(context)
        )
        return

    debt_type = person_debts[0]['type']
    direction = t("iou.person_direction_lent", context) if debt_type == 'lent' else t("iou.person_direction_borrowed", context)

    header = t("iou.person_header_open", context, person=person_name, direction=direction)
    ledger_text = _format_person_ledger(person_debts, context, is_settled=False)

    await query.edit_message_text(
        text=header + ledger_text,
        parse_mode='HTML',
        reply_markup=keyboards.iou_person_actions_keyboard(person_name, debt_type, context, is_settled=False)
    )


@authenticate_user # <-- MODIFIED
async def iou_person_detail_settled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a unified ledger of all settled debts for a specific person."""
    query = update.callback_query
    await query.answer()
    _, _, _, person_name = query.data.split(':')

    # --- MODIFICATION: Get user_id and pass to API ---
    user_id = context.user_data['user_profile']['_id']
    person_debts = api_client.get_all_settled_debts_by_person(person_name, user_id)
    # ---

    if not person_debts:
        await query.edit_message_text(
            t("iou.person_fail_settled", context, person=person_name),
            reply_markup=keyboards.iou_menu_keyboard(context)
        )
        return

    debt_type = person_debts[0]['type']
    direction = t("iou.person_direction_lent_past", context) if debt_type == 'lent' else t("iou.person_direction_borrowed_past", context)

    header = t("iou.person_header_settled", context, person=person_name, direction=direction)
    ledger_text = _format_person_ledger(person_debts, context, is_settled=True)

    await query.edit_message_text(
        text=header + ledger_text,
        parse_mode='HTML',
        reply_markup=keyboards.iou_person_actions_keyboard(person_name, debt_type, context, is_settled=True)
    )


@authenticate_user # <-- MODIFIED
async def iou_manage_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays a list of individual debts for management (Edit/Cancel)."""
    query = update.callback_query
    await query.answer()
    _, _, _, person_name, debt_type, is_settled_str = query.data.split(':')
    is_settled = is_settled_str == 'True'

    # --- MODIFICATION: Get user_id and pass to API ---
    user_id = context.user_data['user_profile']['_id']
    if is_settled:
        person_debts = api_client.get_all_settled_debts_by_person(person_name, user_id)
    else:
        person_debts = api_client.get_all_debts_by_person(person_name, user_id)
    # ---

    if not person_debts:
        await query.edit_message_text(
            t("iou.manage_fail", context),
            reply_markup=keyboards.iou_menu_keyboard(context)
        )
        return

    await query.edit_message_text(
        t("iou.manage_header", context),
        reply_markup=keyboards.iou_manage_list_keyboard(person_debts, person_name, debt_type, is_settled, context)
    )


@authenticate_user # <-- MODIFIED
async def iou_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows details for a single debt, open or settled."""
    query = update.callback_query
    await query.answer()
    _, _, debt_id, person_name, is_settled_str = query.data.split(':')
    is_settled = is_settled_str == 'True'

    # --- MODIFICATION: Get user_id and pass to API ---
    user_id = context.user_data['user_profile']['_id']
    debt = api_client.get_debt_details(debt_id, user_id)
    # ---

    if not debt:
        await query.edit_message_text(
            t("iou.detail_fail", context),
            reply_markup=keyboards.iou_menu_keyboard(context)
        )
        return

    text = _format_debt_details(debt, context)
    keyboard = keyboards.iou_detail_actions_keyboard(debt_id, person_name, debt['type'], is_settled, debt['status'], context)
    await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=keyboard)


@authenticate_user # <-- MODIFIED
async def debt_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches, displays debt analysis text, and sends charts."""
    query = update.callback_query
    await query.answer(t("iou.analysis_loading", context))
    chat_id = update.effective_chat.id

    # --- MODIFICATION: Get user_id and pass to API ---
    user_id = context.user_data['user_profile']['_id']
    analysis_data = api_client.get_debt_analysis(user_id)
    # ---

    if not analysis_data:
        await query.edit_message_text(
            t("iou.analysis_fail", context),
            reply_markup=keyboards.iou_menu_keyboard(context)
        )
        return

    final_text = _format_debt_analysis_message(analysis_data, context)
    await query.edit_message_text(
        text=final_text,
        parse_mode='HTML',
        reply_markup=keyboards.iou_menu_keyboard(context)
    )

    if overview_pie := _create_debt_overview_pie(analysis_data):
        await context.bot.send_photo(chat_id=chat_id, photo=overview_pie)
    if concentration_bar := _create_debt_concentration_bar(analysis_data):
        await context.bot.send_photo(chat_id=chat_id, photo=concentration_bar)


# --- IOU Add Conversation ---
@authenticate_user # <-- MODIFIED
async def iou_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the IOU conversation by asking for the date."""
    query = update.callback_query
    await query.answer()

    # --- THIS IS THE FIX ---
    user_profile = context.user_data.get('user_profile')
    context.user_data.clear()
    context.user_data['user_profile'] = user_profile
    # --- END FIX ---

    context.user_data['iou_type'] = 'lent' if query.data == 'iou_lent' else 'borrowed'
    await query.message.reply_text(
        t("iou.ask_date", context),
        reply_markup=keyboards.iou_date_keyboard(context)
    )
    return IOU_ASK_DATE

async def iou_received_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the date choice for an IOU."""
    query = update.callback_query
    await query.answer()
    choice = query.data

    prompt = (t("iou.ask_person_lent", context)
              if context.user_data['iou_type'] == 'lent'
              else t("iou.ask_person_borrowed", context))

    if choice == 'iou_date_today':
        await query.message.reply_text(prompt)
        return IOU_PERSON
    elif choice == 'iou_date_yesterday':
        yesterday = datetime.now(PHNOM_PENH_TZ).date() - timedelta(days=1)
        context.user_data['timestamp'] = datetime.combine(yesterday, time(12, 0), tzinfo=PHNOM_PENH_TZ).isoformat()
        await query.message.reply_text(prompt)
        return IOU_PERSON
    elif choice == 'iou_date_custom':
        await query.message.reply_text(t("iou.ask_date_custom", context))
        return IOU_CUSTOM_DATE


async def iou_received_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the custom date input for an IOU."""
    try:
        custom_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['timestamp'] = datetime.combine(custom_date, time(12, 0), tzinfo=PHNOM_PENH_TZ).isoformat()
        prompt = (t("iou.ask_person_lent", context)
                  if context.user_data['iou_type'] == 'lent'
                  else t("iou.ask_person_borrowed", context))
        await update.message.reply_text(prompt)
        return IOU_PERSON
    except ValueError:
        await update.message.reply_text(t("forgot.invalid_date", context))
        return IOU_CUSTOM_DATE


async def iou_received_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['iou_person'] = update.message.text.strip().title()
    await update.message.reply_text(t("iou.ask_amount", context))
    return IOU_AMOUNT


async def iou_received_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount_str = update.message.text
        amount, currency = parse_amount_and_currency(amount_str)
        context.user_data['iou_amount'] = amount
        context.user_data['iou_currency'] = currency

        if currency in ['USD', 'KHR']:
            amount_display = f"{amount:,.0f} {currency}" if currency == 'KHR' else f"${amount:,.2f}"
            await update.message.reply_text(
                t("iou.ask_purpose", context, amount_display=amount_display),
                parse_mode='HTML'
            )
            return IOU_PURPOSE

        # Fallback
        await update.message.reply_text(
            t("iou.ask_currency", context),
            reply_markup=keyboards.currency_keyboard(context)
        )
        return IOU_CURRENCY
    except ValueError:
        await update.message.reply_text(t("iou.invalid_amount", context))
        return IOU_AMOUNT


async def iou_received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    currency = query.data.split('_')[1]
    context.user_data['iou_currency'] = currency
    await query.message.reply_text(
        t("iou.ask_purpose_curr", context, currency=currency),
        parse_mode='HTML'
    )
    return IOU_PURPOSE


async def iou_received_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the purpose and saves the new IOU."""
    user_id = context.user_data['user_profile']['_id']
    debt_data = {
        "type": context.user_data.get('iou_type'),
        "person": context.user_data.get('iou_person'),
        "amount": context.user_data.get('iou_amount'),
        "currency": context.user_data.get('iou_currency'),
        "purpose": update.message.text.strip(),
        "timestamp": context.user_data.get('timestamp')
    }

    response = api_client.add_debt(debt_data, user_id)
    base_text = t("iou.success", context) if response else t("iou.fail", context)

    summary_text = format_summary_message(
        api_client.get_detailed_summary(user_id), context
    )

    await update.message.reply_text(
        base_text + summary_text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard(context)
    )
    context.user_data.clear()
    return ConversationHandler.END


# --- Lump-Sum Repayment Conversation (from button) ---
@authenticate_user # <-- MODIFIED
async def repay_lump_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the lump-sum repayment conversation."""
    query = update.callback_query
    await query.answer()

    # --- THIS IS THE FIX ---
    user_profile = context.user_data.get('user_profile')
    context.user_data.clear()
    context.user_data['user_profile'] = user_profile
    # --- END FIX ---

    _, _, person, debt_type = query.data.split(':')
    context.user_data.update({
        'lump_repay_person': person,
        'lump_repay_debt_type': debt_type
    })

    prompt_key = "iou.repay_ask_amount_lent" if debt_type == 'lent' else "iou.repay_ask_amount_borrowed"
    prompt = t(prompt_key, context, person=person)

    await query.message.reply_text(prompt)
    return REPAY_LUMP_AMOUNT


async def received_lump_repayment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and processes the lump-sum repayment amount."""
    try:
        user_id = context.user_data['user_profile']['_id']
        amount_str = update.message.text
        amount, currency = parse_amount_and_currency(amount_str)

        person = context.user_data['lump_repay_person']
        debt_type = context.user_data['lump_repay_debt_type']

        response = api_client.record_lump_sum_repayment(
            person, currency, amount, debt_type, user_id, timestamp=None
        )

        base_text = (t("iou.repay_success", context, message=response['message'])
                     if 'message' in response
                     else t("iou.repay_fail", context, error=response.get('error', 'Unknown error')))

        summary_text = format_summary_message(
            api_client.get_detailed_summary(user_id), context
        )

        await update.message.reply_text(
            base_text + summary_text,
            parse_mode='HTML',
            reply_markup=keyboards.main_menu_keyboard(context)
        )
        return ConversationHandler.END
    except (ValueError, TypeError):
        await update.message.reply_text(t("iou.repay_invalid_amount", context))
        return REPAY_LUMP_AMOUNT

# --- NEW: Debt Edit/Cancel Handlers ---

@authenticate_user # <-- MODIFIED
async def iou_manage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the edit/cancel menu for a specific debt."""
    query = update.callback_query
    await query.answer()
    _, _, _, debt_id, person, is_settled_str = query.data.split(':')
    await query.edit_message_text(
        t("iou.manage_menu_header", context, person=person),
        reply_markup=keyboards.iou_manage_keyboard(debt_id, person, is_settled_str, context)
    )


@authenticate_user # <-- MODIFIED
async def iou_cancel_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks for confirmation before canceling a debt."""
    query = update.callback_query
    await query.answer()
    _, _, _, debt_id, person, is_settled_str = query.data.split(':')
    await query.edit_message_text(
        t("iou.cancel_prompt", context),
        parse_mode='Markdown',
        reply_markup=keyboards.iou_cancel_confirm_keyboard(debt_id, person, is_settled_str, context)
    )


@authenticate_user # <-- MODIFIED
async def iou_cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirms and cancels the debt."""
    query = update.callback_query
    await query.answer(t("iou.cancel_confirm", context))

    user_id = context.user_data['user_profile']['_id']
    debt_id = query.data.split(':')[-1]
    response = api_client.cancel_debt(debt_id, user_id)

    if 'message' in response:
        base_text = t("iou.cancel_success", context, message=response['message'])
    else:
        base_text = t("iou.cancel_fail", context, error=response.get('error', 'Unknown error'))

    summary_text = format_summary_message(
        api_client.get_detailed_summary(user_id), context
    )

    await query.edit_message_text(
        base_text + summary_text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard(context)
    )
    return ConversationHandler.END


# --- NEW: Debt Edit Conversation ---

@authenticate_user # <-- MODIFIED
async def iou_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation to edit a debt's field."""
    query = update.callback_query
    await query.answer()

    # --- THIS IS THE FIX ---
    user_profile = context.user_data.get('user_profile')
    context.user_data.clear()
    context.user_data['user_profile'] = user_profile
    # --- END FIX ---

    _, _, field, debt_id = query.data.split(':')

    context.user_data['iou_edit_debt_id'] = debt_id
    context.user_data['iou_edit_field'] = field

    if field == 'person':
        await query.message.reply_text(t("iou.edit_ask_person", context))
    elif field == 'purpose':
        await query.message.reply_text(t("iou.edit_ask_purpose", context))

    return IOU_EDIT_GET_VALUE


async def iou_edit_received_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the new value and updates the debt."""
    user_id = context.user_data['user_profile']['_id']
    debt_id = context.user_data.get('iou_edit_debt_id')
    field = context.user_data.get('iou_edit_field')
    new_value = update.message.text

    if not debt_id or not field:
        await update.message.reply_text(
            t("iou.edit_error_context", context),
            reply_markup=keyboards.main_menu_keyboard(context)
        )
        return ConversationHandler.END

    response = api_client.update_debt(debt_id, {field: new_value}, user_id)

    if 'message' in response:
        base_text = t("iou.edit_success", context, message=response['message'])
    else:
        base_text = t("iou.edit_fail", context, error=response.get('error', 'Unknown error'))

    summary_text = format_summary_message(
        api_client.get_detailed_summary(user_id), context
    )

    await update.message.reply_text(
        base_text + summary_text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard(context)
    )
    context.user_data.clear()
    return ConversationHandler.END
# --- End of modified file ---