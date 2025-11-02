# --- Start of file: telegram_bot/handlers/iou.py ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import keyboards
import api_client
from decorators import restricted
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from .helpers import format_summary_message
from .command_handler import parse_amount_and_currency

# Conversation states
(
    IOU_ASK_DATE, IOU_CUSTOM_DATE, IOU_PERSON, IOU_AMOUNT, IOU_CURRENCY, IOU_PURPOSE,
    REPAY_LUMP_AMOUNT,
    IOU_EDIT_GET_VALUE # New state for edit conversation
) = range(8)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")

def _format_debt_details(debt):
    """Helper to format the full details of a debt, including repayments."""
    direction = "Owes you" if debt['type'] == 'lent' else "You owe"
    purpose_text = f"<b>Purpose:</b> {debt['purpose']}\n" if debt.get('purpose') else ""
    created_date = datetime.fromisoformat(debt['created_at'].replace('Z', '+00:00')).astimezone(PHNOM_PENH_TZ).strftime(
        '%d %b %Y, %I:%M %p')
    amount_format = ",.0f" if debt['currency'] == 'KHR' else ",.2f"

    text_lines = [
        f"<b>Debt Details (Status: {debt['status'].title()})</b>\n",
        f"<b>Person:</b> {debt['person']} ({direction})",
        f"<b>Date Created:</b> {created_date}",
        purpose_text,
        f"<b>Original Amount:</b> {debt['originalAmount']:{amount_format}} {debt['currency']}",
        f"<b>Remaining Balance:</b> {debt['remainingAmount']:{amount_format}} {debt['currency']}\n"
    ]

    repayments = debt.get('repayments', [])
    if repayments:
        text_lines.append("<b>Repayment History:</b>")
        for rep in repayments:
            rep_date = datetime.fromisoformat(rep['date'].replace('Z', '+00:00')).astimezone(PHNOM_PENH_TZ).strftime('%d %b %Y')
            text_lines.append(f"  - {rep['amount']:{amount_format}} {debt['currency']} on {rep_date}")

    return "\n".join(text_lines)

# --- NEW HELPER ---
def _format_person_ledger(person_debts, is_settled=False):
    """Formats all debts and repayments for one person into a single chronological list."""

    if not person_debts:
        return "No debts found for this person."

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

    # Sort all items by date
    ledger_items.sort(key=lambda x: x[0])

    # Format the final string
    date_format = '%d %b %Y'
    last_date = None
    ledger_lines = []

    # Header
    if not is_settled:
        header_lines = ["<b>Total Remaining:</b>"]
        if total_remaining_usd > 0:
            header_lines.append(f"  💵 {total_remaining_usd:,.2f} USD")
        if total_remaining_khr > 0:
            header_lines.append(f"  ៛ {total_remaining_khr:,.0f} KHR")
        if total_remaining_usd == 0 and total_remaining_khr == 0:
            header_lines.append("  None")
        ledger_lines.append("\n".join(header_lines) + "\n")

    ledger_lines.append("<b>Full Ledger (Oldest First):</b>")

    for item_dt, item_text, item_currency in ledger_items:
        current_date_str = item_dt.astimezone(PHNOM_PENH_TZ).strftime(date_format)
        if current_date_str != last_date:
            ledger_lines.append(f"\n<u>{current_date_str}</u>")
            last_date = current_date_str
        ledger_lines.append(item_text)

    return "\n".join(ledger_lines)


# --- IOU Menu & Standalone Handlers ---
@restricted
async def iou_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the IOU management menu."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="🤝 Let's manage your IOUs.", reply_markup=keyboards.iou_menu_keyboard())


@restricted
async def iou_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a summary list of all open debts, grouped by person."""
    query = update.callback_query
    await query.answer()
    grouped_debts = api_client.get_open_debts()
    text = "Here is a summary of your **open** debts.\nSelect one to see details:"
    keyboard = keyboards.iou_list_keyboard(grouped_debts, is_settled=False)
    if not grouped_debts:
        text = "You have no open debts! 👍"
        keyboard = keyboards.iou_menu_keyboard()
    await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode='Markdown')

# --- NEW FUNCTION ---
@restricted
async def iou_view_settled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a summary list of all settled debts, grouped by person."""
    query = update.callback_query
    await query.answer()
    grouped_debts = api_client.get_settled_debts_grouped()
    text = "Here is a summary of your **settled/canceled** debts.\nSelect one to see details:"
    keyboard = keyboards.iou_list_keyboard(grouped_debts, is_settled=True)
    if not grouped_debts:
        text = "You have no settled debts."
        keyboard = keyboards.iou_menu_keyboard()
    await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode='Markdown')


@restricted
async def iou_person_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ --- THIS FUNCTION IS REWRITTEN --- """
    """Shows a unified ledger of all open debts for a specific person."""
    query = update.callback_query
    await query.answer()
    # Callback format: iou:person:open:{person_name}
    _, _, _, person_name = query.data.split(':')

    person_debts = api_client.get_all_debts_by_person(person_name)

    if not person_debts:
        await query.edit_message_text(f"❌ Could not find any open debts for {person_name}.",
                                      reply_markup=keyboards.iou_menu_keyboard())
        return

    debt_type = person_debts[0]['type']
    direction = "owes you" if debt_type == 'lent' else "you owe"

    header = f"<b>Open Debts for {person_name}</b> ({direction})\n\n"
    ledger_text = _format_person_ledger(person_debts, is_settled=False)

    await query.edit_message_text(
        text=header + ledger_text,
        parse_mode='HTML',
        reply_markup=keyboards.iou_person_actions_keyboard(person_name, debt_type, is_settled=False)
    )

# --- NEW FUNCTION ---
@restricted
async def iou_person_detail_settled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a unified ledger of all settled debts for a specific person."""
    query = update.callback_query
    await query.answer()
    # Callback format: iou:person:settled:{person_name}
    _, _, _, person_name = query.data.split(':')
    person_debts = api_client.get_all_settled_debts_by_person(person_name)

    if not person_debts:
        await query.edit_message_text(f"❌ Could not find any settled debts for {person_name}.",
                                      reply_markup=keyboards.iou_menu_keyboard())
        return

    debt_type = person_debts[0]['type']
    direction = "owed you" if debt_type == 'lent' else "you owed"

    header = f"<b>Settled Debts for {person_name}</b> ({direction})\n\n"
    ledger_text = _format_person_ledger(person_debts, is_settled=True)

    await query.edit_message_text(
        text=header + ledger_text,
        parse_mode='HTML',
        reply_markup=keyboards.iou_person_actions_keyboard(person_name, debt_type, is_settled=True)
    )

# --- NEW FUNCTION ---
@restricted
async def iou_manage_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays a list of individual debts for management (Edit/Cancel)."""
    query = update.callback_query
    await query.answer()
    # Callback: iou:manage:list:{person_name}:{debt_type}:{is_settled}
    _, _, _, person_name, debt_type, is_settled_str = query.data.split(':')
    is_settled = is_settled_str == 'True'

    if is_settled:
        person_debts = api_client.get_all_settled_debts_by_person(person_name)
    else:
        person_debts = api_client.get_all_debts_by_person(person_name)

    if not person_debts:
        await query.edit_message_text("❌ No debts found to manage.", reply_markup=keyboards.iou_menu_keyboard())
        return

    await query.edit_message_text(
        "Select a specific debt to manage:",
        reply_markup=keyboards.iou_manage_list_keyboard(person_debts, person_name, debt_type, is_settled)
    )


@restricted
async def iou_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Shows details for a single debt, open or settled.
    """
    query = update.callback_query
    await query.answer()
    # Callback format: iou:detail:{debt_id}:{person_name}:{is_settled}
    _, _, debt_id, person_name, is_settled_str = query.data.split(':')
    is_settled = is_settled_str == 'True'

    debt = api_client.get_debt_details(debt_id)
    if not debt:
        await query.edit_message_text("❌ Error: Could not find this debt.", reply_markup=keyboards.iou_menu_keyboard())
        return

    text = _format_debt_details(debt)

    # Show different keyboard based on whether the debt is open or settled
    keyboard = keyboards.iou_detail_actions_keyboard(debt_id, person_name, debt['type'], is_settled, debt['status'])

    await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=keyboard)


@restricted
async def debt_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays debt analysis."""
    query = update.callback_query
    await query.answer("Analyzing debts...")
    analysis_data = api_client.get_debt_analysis()
    if not analysis_data:
        await query.edit_message_text("Could not perform debt analysis.", reply_markup=keyboards.iou_menu_keyboard())
        return

    lent_by = [d for d in analysis_data.get('concentration', []) if d['type'] == 'lent']
    borrow_from = [d for d in analysis_data.get('concentration', []) if d['type'] == 'borrowed']

    lent_text = "\n<b>Top People You've Lent To:</b>\n"
    lent_text += "\n".join(
        [f"    - {item['person']}: ${item['total']:,.2f}" for item in lent_by[:3]]) or "    - No one owes you money.\n"

    borrow_text = "\n<b>Top People You've Borrowed From:</b>\n"
    borrow_text += "\n".join([f"    - {item['person']}: ${item['total']:,.2f}" for item in
                              borrow_from[:3]]) or "    - You don't owe anyone money.\n"

    aging_text = "\n<b>Oldest Outstanding Debts (Avg. Age):</b>\n"
    aging_data = analysis_data.get('aging', [])
    aging_text += "\n".join(
        [f"    - {item['_id']}: {item['averageAgeDays']:.0f} days ({item['count']} loans)" for item in
         aging_data[:3]]) or "    - No open debts to analyze.\n"

    final_text = "🔬 <b>Debt Analysis</b>\n" + lent_text + borrow_text + aging_text
    await query.edit_message_text(text=final_text, parse_mode='HTML', reply_markup=keyboards.iou_menu_keyboard())


# --- IOU Add Conversation ---
@restricted
async def iou_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the IOU conversation by asking for the date."""
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data['iou_type'] = 'lent' if query.data == 'iou_lent' else 'borrowed'
    await query.message.reply_text("When did this happen?", reply_markup=keyboards.iou_date_keyboard())
    return IOU_ASK_DATE


async def iou_received_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the date choice for an IOU."""
    query = update.callback_query
    await query.answer()
    choice = query.data
    prompt = "Who did you lend money to?" if context.user_data[
                                                 'iou_type'] == 'lent' else "Who did you borrow money from?"

    if choice == 'iou_date_today':
        await query.message.reply_text(prompt)
        return IOU_PERSON
    elif choice == 'iou_date_yesterday':
        yesterday = datetime.now(PHNOM_PENH_TZ).date() - timedelta(days=1)
        context.user_data['timestamp'] = datetime.combine(yesterday, time(12, 0), tzinfo=PHNOM_PENH_TZ).isoformat()
        await query.message.reply_text(prompt)
        return IOU_PERSON
    elif choice == 'iou_date_custom':
        await query.message.reply_text("Please enter the date in YYYY-MM-DD format.")
        return IOU_CUSTOM_DATE


async def iou_received_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the custom date input for an IOU."""
    try:
        custom_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['timestamp'] = datetime.combine(custom_date, time(12, 0), tzinfo=PHNOM_PENH_TZ).isoformat()
        prompt = "Who did you lend money to?" if context.user_data[
                                                     'iou_type'] == 'lent' else "Who did you borrow money from?"
        await update.message.reply_text(prompt)
        return IOU_PERSON
    except ValueError:
        await update.message.reply_text("Invalid format. Please use YYYY-MM-DD.")
        return IOU_CUSTOM_DATE


async def iou_received_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['iou_person'] = update.message.text.strip().title()
    await update.message.reply_text("How much?")
    return IOU_AMOUNT


async def iou_received_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        context.user_data['iou_amount'] = amount

        if amount < 100:
            currency = "USD"
            context.user_data['iou_currency'] = currency
            await update.message.reply_text(
                f"Amount: <b>{amount:,.2f} USD</b> (auto-selected)\n\nWhat was this for? (e.g., Lunch, Deposit)",
                parse_mode='HTML')
            return IOU_PURPOSE
        else:
            await update.message.reply_text("Which currency?", reply_markup=keyboards.currency_keyboard())
            return IOU_CURRENCY
    except ValueError:
        await update.message.reply_text("Please enter a valid number for the amount.")
        return IOU_AMOUNT


async def iou_received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['iou_currency'] = query.data.split('_')[1]
    await query.message.reply_text(
        f"Currency: <b>{context.user_data['iou_currency']}</b>\n\nWhat was this for? (e.g., Lunch, Deposit)",
        parse_mode='HTML')
    return IOU_PURPOSE


async def iou_received_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the purpose and saves the new IOU."""
    debt_data = {
        "type": context.user_data.get('iou_type'),
        "person": context.user_data.get('iou_person'),
        "amount": context.user_data.get('iou_amount'),
        "currency": context.user_data.get('iou_currency'),
        "purpose": update.message.text.strip(),
        "timestamp": context.user_data.get('timestamp')
    }
    response = api_client.add_debt(debt_data)
    base_text = "✅ Debt successfully recorded!" if response else "❌ Failed to record debt."
    summary_text = format_summary_message(api_client.get_detailed_summary())
    await update.message.reply_text(base_text + summary_text, parse_mode='HTML',
                                    reply_markup=keyboards.main_menu_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


# --- Lump-Sum Repayment Conversation (from button) ---
@restricted
async def repay_lump_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the lump-sum repayment conversation."""
    query = update.callback_query
    await query.answer()
    # --- FIX: Parse new callback data format ---
    _, _, person, debt_type = query.data.split(':')
    context.user_data.update({
        'lump_repay_person': person,
        'lump_repay_debt_type': debt_type
    })

    prompt = f"How much did {person} repay you (in USD or KHR)?" if debt_type == 'lent' else f"How much did you repay {person} (in USD or KHR)?"
    await query.message.reply_text(prompt)
    return REPAY_LUMP_AMOUNT


async def received_lump_repayment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and processes the lump-sum repayment amount."""
    try:
        # --- FIX: Parse amount and currency from text ---
        amount_str = update.message.text
        amount, currency = parse_amount_and_currency(amount_str)

        person = context.user_data['lump_repay_person']
        debt_type = context.user_data['lump_repay_debt_type']

        # --- FIX: Call api client with correct args ---
        response = api_client.record_lump_sum_repayment(person, currency, amount, debt_type)

        base_text = f"✅ {response['message']}" if 'message' in response else f"❌ Error: {response.get('error', 'Unknown error')}"
        summary_text = format_summary_message(api_client.get_detailed_summary())
        await update.message.reply_text(base_text + summary_text, parse_mode='HTML',
                                        reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END
    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid amount and currency (e.g., '50.50' or '20000khr').")
        return REPAY_LUMP_AMOUNT

# --- NEW: Debt Edit/Cancel Handlers ---

@restricted
async def iou_manage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the edit/cancel menu for a specific debt."""
    query = update.callback_query
    await query.answer()
    # iou:manage:detail:{debt_id}:{person}:{is_settled}
    _, _, _, debt_id, person, is_settled_str = query.data.split(':')

    await query.edit_message_text(
        f"What would you like to do for this debt with {person}?",
        reply_markup=keyboards.iou_manage_keyboard(debt_id, person, is_settled_str)
    )

@restricted
async def iou_cancel_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks for confirmation before canceling a debt."""
    query = update.callback_query
    await query.answer()
    # iou:cancel:prompt:{debt_id}:{person}:{is_settled}
    _, _, _, debt_id, person, is_settled_str = query.data.split(':')
    await query.edit_message_text(
        "⚠️ **Are you sure you want to cancel this debt?**\n\n"
        "This will create a reversing transaction to balance your accounts and mark the debt as 'Canceled'. "
        "This action cannot be undone.",
        parse_mode='Markdown',
        reply_markup=keyboards.iou_cancel_confirm_keyboard(debt_id, person, is_settled_str)
    )

@restricted
async def iou_cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirms and cancels the debt."""
    query = update.callback_query
    await query.answer("Canceling...")
    # iou:cancel:confirm:{debt_id}
    debt_id = query.data.split(':')[-1]

    response = api_client.cancel_debt(debt_id)

    if 'message' in response:
        base_text = f"✅ {response['message']}"
    else:
        base_text = f"❌ Error: {response.get('error', 'Unknown error')}"

    summary_text = format_summary_message(api_client.get_detailed_summary())
    await query.edit_message_text(
        base_text + summary_text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard()
    )
    return ConversationHandler.END # End any conversation, just in case

# --- NEW: Debt Edit Conversation ---

@restricted
async def iou_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation to edit a debt's field."""
    query = update.callback_query
    await query.answer()
    # iou:edit:{field}:{debt_id}
    _, _, field, debt_id = query.data.split(':')

    context.user_data['iou_edit_debt_id'] = debt_id
    context.user_data['iou_edit_field'] = field

    if field == 'person':
        await query.message.reply_text("Please enter the new person's name:")
    elif field == 'purpose':
        await query.message.reply_text("Please enter the new purpose:")

    return IOU_EDIT_GET_VALUE

async def iou_edit_received_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the new value and updates the debt."""
    debt_id = context.user_data.get('iou_edit_debt_id')
    field = context.user_data.get('iou_edit_field')
    new_value = update.message.text

    if not debt_id or not field:
        await update.message.reply_text("Error: Conversation context lost. Please try again.", reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END

    response = api_client.update_debt(debt_id, {field: new_value})

    if 'message' in response:
        base_text = f"✅ {response['message']}"
    else:
        base_text = f"❌ Error: {response.get('error', 'Unknown error')}"

    summary_text = format_summary_message(api_client.get_detailed_summary())
    await update.message.reply_text(
        base_text + summary_text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END