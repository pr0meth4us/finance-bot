# --- Start of file: telegram_bot/handlers/iou.py ---

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import keyboards
import api_client
from decorators import restricted
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from .helpers import format_summary_message

# Conversation states
(
    IOU_ASK_DATE, IOU_CUSTOM_DATE, IOU_PERSON, IOU_AMOUNT, IOU_CURRENCY, IOU_PURPOSE,
    REPAY_LUMP_AMOUNT
) = range(7)

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")


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
    text = "Here is a summary of debts by person.\nSelect one to see details:"
    keyboard = keyboards.iou_list_keyboard(grouped_debts)
    if not grouped_debts:
        text = "You have no open debts! 👍"
        keyboard = keyboards.iou_menu_keyboard()
    await query.edit_message_text(text=text, reply_markup=keyboard)


@restricted
async def iou_person_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows all individual debts for a specific person and currency."""
    query = update.callback_query
    await query.answer()
    _, _, person_name, currency = query.data.split(':')
    person_debts = api_client.get_debts_by_person_and_currency(person_name, currency)
    if not person_debts:
        await query.edit_message_text(f"❌ Could not find any open {currency} debts for {person_name}.",
                                      reply_markup=keyboards.iou_menu_keyboard())
        return

    total = sum(d['remainingAmount'] for d in person_debts)

    # --- FIX: Get debt_type and pass it to keyboard ---
    debt_type = person_debts[0]['type']
    direction = "owes you" if debt_type == 'lent' else "you owe"

    amount_format = ",.0f" if currency == 'KHR' else ",.2f"
    text = (
        f"<b>Debts for {person_name}</b> ({direction})\n"
        f"<b>Total Remaining:</b> {total:{amount_format}} {currency}\n\n"
        "Select a specific loan to view, or record a repayment:"
    )
    await query.edit_message_text(text=text, parse_mode='HTML',
                                  reply_markup=keyboards.iou_person_detail_keyboard(person_debts, person_name,
                                                                                    currency, debt_type))


@restricted
async def iou_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows details for a single debt."""
    query = update.callback_query
    await query.answer()
    _, _, debt_id, person_name, currency = query.data.split(':')
    debt = api_client.get_debt_details(debt_id)
    if not debt:
        await query.edit_message_text("❌ Error: Could not find this debt.", reply_markup=keyboards.iou_menu_keyboard())
        return

    direction = "Owes you" if debt['type'] == 'lent' else "You owe"
    purpose_text = f"<b>Purpose:</b> {debt['purpose']}\n" if debt.get('purpose') else ""
    created_date = datetime.fromisoformat(debt['created_at'].replace('Z', '+00:00')).astimezone(PHNOM_PENH_TZ).strftime(
        '%d %b %Y, %I:%M %p')
    amount_format = ",.0f" if debt['currency'] == 'KHR' else ",.2f"
    text = (
        f"<b>Debt Details:</b>\n"
        f"<b>Person:</b> {debt['person']} ({direction})\n"
        f"<b>Date Created:</b> {created_date}\n"
        f"{purpose_text}"
        f"<b>Original Amount:</b> {debt['originalAmount']:{amount_format}} {debt['currency']}\n"
        f"<b>Remaining Balance:</b> {debt['remainingAmount']:{amount_format}} {debt['currency']}"
    )
    await query.edit_message_text(text=text, parse_mode='HTML',
                                  reply_markup=keyboards.iou_detail_keyboard(debt_id, person_name, currency))


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
            # Auto-select USD and skip to purpose
            currency = "USD"
            context.user_data['iou_currency'] = currency
            await update.message.reply_text(
                f"Amount: <b>{amount:,.2f} USD</b> (auto-selected)\n\nWhat was this for? (e.g., Lunch, Deposit)",
                parse_mode='HTML')
            return IOU_PURPOSE
        else:
            # Ask for currency as usual
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


# --- Lump-Sum Repayment Conversation ---
@restricted
async def repay_lump_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the lump-sum repayment conversation."""
    query = update.callback_query
    await query.answer()
    # --- FIX: Parse new callback data format ---
    _, _, person, currency, debt_type = query.data.split(':')
    context.user_data.update({
        'lump_repay_person': person,
        'lump_repay_currency': currency,
        'lump_repay_debt_type': debt_type
    })

    prompt = f"How much did {person} repay you in {currency}?" if debt_type == 'lent' else f"How much did you repay {person} in {currency}?"
    await query.message.reply_text(prompt)
    return REPAY_LUMP_AMOUNT


async def received_lump_repayment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and processes the lump-sum repayment amount."""
    try:
        amount = float(update.message.text)
        person = context.user_data['lump_repay_person']
        currency = context.user_data['lump_repay_currency']
        debt_type = context.user_data['lump_repay_debt_type']

        # --- FIX: Call api client with debt_type ---
        response = api_client.record_lump_sum_repayment(person, currency, amount, debt_type)

        base_text = f"✅ {response['message']}" if 'message' in response else f"❌ Error: {response.get('error', 'Unknown error')}"
        summary_text = format_summary_message(api_client.get_detailed_summary())
        await update.message.reply_text(base_text + summary_text, parse_mode='HTML',
                                        reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END
    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid number for the repayment amount.")
        return REPAY_LUMP_AMOUNT