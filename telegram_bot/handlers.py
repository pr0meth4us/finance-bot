# --- Start of modified file: telegram_bot/handlers.py ---

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import keyboards
import api_client
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from decorators import restricted
from collections import defaultdict
# --- START OF MODIFICATION ---
import io
import matplotlib.pyplot as plt
# --- END OF MODIFICATION ---


# --- Conversation States ---
(
    AMOUNT, CURRENCY, CATEGORY, CUSTOM_CATEGORY, ASK_REMARK, REMARK,
    NEW_RATE,
    IOU_ASK_DATE, IOU_CUSTOM_DATE, IOU_PERSON, IOU_AMOUNT, IOU_CURRENCY, IOU_PURPOSE,
    REPAY_LUMP_AMOUNT,
    SETBALANCE_ACCOUNT, SETBALANCE_AMOUNT,
    FORGOT_DATE, FORGOT_CUSTOM_DATE, FORGOT_TYPE,
    REMINDER_PURPOSE, REMINDER_ASK_DATE, REMINDER_CUSTOM_DATE, REMINDER_ASK_TIME
) = range(23)

CHOOSE_REPORT_PERIOD, REPORT_ASK_START_DATE, REPORT_ASK_END_DATE = range(23, 26)

# --- START OF MODIFICATION ---
# Add new states for the transaction editing conversation
EDIT_CHOOSE_FIELD, EDIT_GET_NEW_VALUE, EDIT_GET_NEW_CATEGORY = range(26, 29)
# --- END OF MODIFICATION ---


PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")


# --- Helper Function ---
def format_summary_message(summary_data):
    """Formats the detailed summary data into a readable string."""
    if not summary_data:
        return ""

    # --- Balances ---
    khr_bal = summary_data.get('balances', {}).get('KHR', 0)
    usd_bal = summary_data.get('balances', {}).get('USD', 0)
    balance_text = f"<b>Balances:</b>\n💵 {usd_bal:,.2f} USD\n៛ {khr_bal:,.0f} KHR"

    # --- Debts ---
    owed_to_you_data = summary_data.get('debts_owed_to_you', [])
    owed_to_you_usd = next((item['total'] for item in owed_to_you_data if item['_id'] == 'USD'), 0)
    owed_to_you_khr = next((item['total'] for item in owed_to_you_data if item['_id'] == 'KHR'), 0)
    owed_to_you_text = f"    💵 {owed_to_you_usd:,.2f} USD\n    ៛ {owed_to_you_khr:,.0f} KHR"

    owed_by_you_data = summary_data.get('debts_owed_by_you', [])
    owed_by_you_usd = next((item['total'] for item in owed_by_you_data if item['_id'] == 'USD'), 0)
    owed_by_you_khr = next((item['total'] for item in owed_by_you_data if item['_id'] == 'KHR'), 0)
    owed_by_you_text = f"    💵 {owed_by_you_usd:,.2f} USD\n    ៛ {owed_by_you_khr:,.0f} KHR"

    debt_text = f"<b>Debts:</b>\n➡️ <b>You are owed:</b>\n{owed_to_you_text}\n⬅️ <b>You owe:</b>\n{owed_by_you_text}"

    # --- Activity Periods ---
    def format_period_line(period_data):
        """Helper to format a single period's income/expense line."""
        income = period_data.get('income', {})
        expense = period_data.get('expense', {})

        income_parts = []
        if income.get('USD', 0) > 0: income_parts.append(f"{income['USD']:,.2f} USD")
        if income.get('KHR', 0) > 0: income_parts.append(f"{income['KHR']:,.0f} KHR")
        income_str = ' & '.join(income_parts) if income_parts else "0"

        expense_parts = []
        if expense.get('USD', 0) > 0: expense_parts.append(f"{expense['USD']:,.2f} USD")
        if expense.get('KHR', 0) > 0: expense_parts.append(f"{expense['KHR']:,.0f} KHR")
        expense_str = ' & '.join(expense_parts) if expense_parts else "0"

        return f"    ⬆️ In: {income_str}\n    ⬇️ Out: {expense_str}"

    periods = summary_data.get('periods', {})
    activity_text = ""
    if periods:
        today_text = f"<b>Today:</b>\n{format_period_line(periods.get('today', {}))}"
        this_week_text = f"<b>This Week:</b>\n{format_period_line(periods.get('this_week', {}))}"
        this_month_text = f"<b>This Month:</b>\n{format_period_line(periods.get('this_month', {}))}"
        activity_text = f"<b>Operational Activity (Excl. Loans):</b>\n{today_text}\n{this_week_text}\n{this_month_text}"

    # --- Combine All Parts ---
    return (
        f"\n\n--- Your Current Status ---\n"
        f"{balance_text}\n\n"
        f"{debt_text}\n\n"
        f"{activity_text}"
    )


# --- Main Commands & Callbacks ---
@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main menu and forcibly ends any active conversation."""
    text = "Welcome to your Personal Finance Assistant!"
    keyboard = keyboards.main_menu_keyboard()
    chat_id = update.effective_chat.id

    if update.callback_query:
        await update.callback_query.answer()
        summary_data = api_client.get_detailed_summary()
        summary_text = format_summary_message(summary_data)
        try:
            await update.callback_query.edit_message_text(
                text + summary_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except Exception:
            pass  # Ignore if message hasn't changed or other minor issues
    else:
        summary_data = api_client.get_detailed_summary()
        summary_text = format_summary_message(summary_data)
        await context.bot.send_message(
            chat_id=chat_id,
            text=text + summary_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )

    return ConversationHandler.END


@restricted
async def quick_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays a quick summary of balances and debts."""
    query = update.callback_query
    await query.answer("Fetching summary...")

    summary_data = api_client.get_detailed_summary()
    summary_text = format_summary_message(summary_data)
    text = "🔍 Here is your quick summary:" + summary_text

    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard()
    )


# --- START OF MODIFICATION ---
# --- Report Generation Conversation ---

def _format_report_summary_message(data):
    """Formats the detailed report data into a readable string."""
    summary = data.get('summary', {})
    income = summary.get('totalIncomeUSD', 0)
    expense = summary.get('totalExpenseUSD', 0)
    net = summary.get('netSavingsUSD', 0)

    start_date = datetime.fromisoformat(data['startDate']).strftime('%b %d, %Y')
    end_date = datetime.fromisoformat(data['endDate']).strftime('%b %d, %Y')

    header = f"📊 <b>Financial Report</b>\n🗓️ <i>{start_date} to {end_date}</i>\n\n"
    summary_text = (
        f"<b>Summary (in USD):</b>\n"
        f"⬆️ Total Income: ${income:,.2f}\n"
        f"⬇️ Total Expense: ${expense:,.2f}\n"
        f"<b>Net: ${net:,.2f}</b> {'✅' if net >= 0 else '🔻'}\n\n"
    )

    expense_breakdown = data.get('expenseBreakdown', [])
    expense_text = "<b>Top Expenses:</b>\n"
    if expense_breakdown:
        for item in expense_breakdown[:5]: # Show top 5
            expense_text += f"    - {item['category']}: ${item['totalUSD']:,.2f}\n"
    else:
        expense_text += "    - No expenses recorded.\n"

    return header + summary_text + expense_text


def _create_income_expense_chart(data):
    """Creates a simple bar chart comparing income and expense."""
    summary = data.get('summary', {})
    income = summary.get('totalIncomeUSD', 0)
    expense = summary.get('totalExpenseUSD', 0)

    if income == 0 and expense == 0:
        return None

    labels = ['Income', 'Expense']
    values = [income, expense]
    colors = ['#4CAF50', '#F44336'] # Green for income, Red for expense

    fig, ax = plt.subplots(figsize=(6, 5))
    bars = ax.bar(labels, values, color=colors)
    ax.set_ylabel('Amount (USD)')
    ax.set_title('Income vs. Expense')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)


    # Add values on top of bars
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval, f'${yval:,.2f}', va='bottom', ha='center')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf.getvalue()


async def _generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE, start_date, end_date):
    """Shared logic to generate and send report summary and chart."""
    chat_id = update.effective_chat.id
    loading_text = f"📈 Generating your report for {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}..."

    message_to_edit = update.callback_query.message if update.callback_query else update.message

    try:
        await message_to_edit.edit_text(text=loading_text)
    except Exception: # Might fail if it's not a callback, so we send a new message
        loading_message = await context.bot.send_message(chat_id=chat_id, text=loading_text)
        message_to_edit = loading_message


    report_data = api_client.get_detailed_report(start_date, end_date)

    try:
        await message_to_edit.delete()
    except Exception:
        pass  # Ignore deletion errors

    if report_data:
        # 1. Format and send the text summary
        summary_message = _format_report_summary_message(report_data)
        await context.bot.send_message(chat_id=chat_id, text=summary_message, parse_mode='HTML')

        # 2. Generate and send the chart
        chart_image = _create_income_expense_chart(report_data)
        if chart_image:
            await context.bot.send_photo(chat_id=chat_id, photo=chart_image)

        # 3. Send final message
        await context.bot.send_message(
            chat_id=chat_id,
            text="Report complete! What's next?",
            reply_markup=keyboards.main_menu_keyboard()
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Could not generate report. No operational data found for this period.",
            reply_markup=keyboards.main_menu_keyboard()
        )
# --- END OF MODIFICATION ---

@restricted
async def report_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the menu for selecting a report period. Entry point for conversation."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "What period would you like a report for?",
        reply_markup=keyboards.report_period_keyboard()
    )
    return CHOOSE_REPORT_PERIOD


@restricted
async def process_report_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles standard period selection or transitions to custom date entry."""
    query = update.callback_query
    await query.answer()

    callback_prefix = "report_period_"
    try:
        period = query.data[len(callback_prefix):]
    except Exception:
        return ConversationHandler.END  # Safety exit

    today = datetime.now(PHNOM_PENH_TZ).date()
    start_date, end_date = None, None

    if period == "today":
        start_date = end_date = today
    elif period == "this_week":
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == "last_week":
        end_date = today - timedelta(days=today.weekday() + 1)
        start_date = end_date - timedelta(days=6)
    elif period == "this_month":
        start_date = today.replace(day=1)
        next_month_first_day = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month_first_day - timedelta(days=1)
    elif period == "custom":
        await query.edit_message_text("Please enter the start date (YYYY-MM-DD):")
        return REPORT_ASK_START_DATE

    if start_date and end_date:
        await _generate_report(update, context, start_date, end_date)
        return ConversationHandler.END
    else:
        await query.edit_message_text("Invalid selection.", reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END


@restricted
async def received_report_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and validates the custom start date."""
    date_str = update.message.text
    try:
        start_date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        context.user_data['report_start_date'] = start_date_obj
        await update.message.reply_text(
            f"Start date set to {start_date_obj.strftime('%Y-%m-%d')}.\nNow, please enter the end date (YYYY-MM-DD):")
        return REPORT_ASK_END_DATE
    except ValueError:
        await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD.")
        return REPORT_ASK_START_DATE


@restricted
async def received_report_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives validates end date, and generates the report."""
    date_str = update.message.text
    try:
        end_date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        start_date_obj = context.user_data.get('report_start_date')

        if not start_date_obj:
            await update.message.reply_text("Error: Start date not found. Cancelling operation.",
                                            reply_markup=keyboards.main_menu_keyboard())
            return ConversationHandler.END

        if end_date_obj < start_date_obj:
            await update.message.reply_text(
                "End date cannot be earlier than start date. Please enter the end date again:")
            return REPORT_ASK_END_DATE

        await _generate_report(update, context, start_date_obj, end_date_obj)

    except ValueError:
        await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD.")
        return REPORT_ASK_END_DATE
    finally:
        context.user_data.pop('report_start_date', None)

    return ConversationHandler.END


# --- Rate Update Conversation ---
@restricted
async def update_rate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation to update the exchange rate."""
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Please enter the new exchange rate for 1 USD to KHR (e.g., 4100)."
    )
    return NEW_RATE


async def received_new_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and saves the new exchange rate."""
    try:
        new_rate = float(update.message.text)
        response = api_client.update_exchange_rate(new_rate)
        if response:
            await update.message.reply_text(f"✅ {response['message']}", reply_markup=keyboards.main_menu_keyboard())
        else:
            await update.message.reply_text("❌ Failed to update the rate.", reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END
    except (ValueError, TypeError):
        await update.message.reply_text("Invalid number. Please enter a valid rate (e.g., 4100).")
        return NEW_RATE


# --- Transaction History & Management ---
@restricted
async def history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays a list of recent transactions to manage."""
    query = update.callback_query
    await query.answer()
    transactions = api_client.get_recent_transactions()
    text_to_send = "Select a transaction to manage:"
    reply_markup_to_send = keyboards.history_keyboard(transactions)

    if not transactions:
        text_to_send = "No recent transactions found."
        reply_markup_to_send = keyboards.main_menu_keyboard()

    # We need to edit the existing message if we came from a back button
    if query.message.text != text_to_send:
        await query.edit_message_text(
            text=text_to_send,
            reply_markup=reply_markup_to_send
        )


@restricted
async def manage_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows options for a selected transaction."""
    query = update.callback_query
    await query.answer()
    tx_id = query.data.split('_')[-1]

    tx_details = api_client.get_transaction_details(tx_id)
    if not tx_details:
        await query.edit_message_text("Error: Could not fetch transaction details.",
                                      reply_markup=keyboards.history_keyboard([]))
        return

    tx_type_emoji = "⬇️ Expense" if tx_details.get('type') == 'expense' else "⬆️ Income"
    amount = tx_details.get('amount', 0)
    currency = tx_details.get('currency', '')
    category = tx_details.get('categoryId', 'N/A')
    description = tx_details.get('description', 'No description')

    # Format timestamp for display
    created_date_obj = datetime.fromisoformat(tx_details['timestamp'].replace('Z', '+00:00'))
    created_date_str = created_date_obj.astimezone(PHNOM_PENH_TZ).strftime('%d %b %Y, %I:%M %p')

    text = (
        f"<b>Transaction Details:</b>\n\n"
        f"<b>Type:</b> {tx_type_emoji}\n"
        f"<b>Amount:</b> {amount:,.2f} {currency}\n"
        f"<b>Category:</b> {category}\n"
        f"<b>Description:</b> {description}\n"
        f"<b>Date:</b> {created_date_str}\n\n"
        "What would you like to do?"
    )

    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.manage_tx_keyboard(tx_id)
    )


@restricted
async def delete_transaction_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks for confirmation before deleting a transaction."""
    query = update.callback_query
    await query.answer()
    tx_id = query.data.split('_')[-1]
    await query.edit_message_text(
        text="⚠️ Are you sure you want to delete this transaction? This action cannot be undone.",
        reply_markup=keyboards.confirm_delete_keyboard(tx_id)
    )


@restricted
async def delete_transaction_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deletes the transaction after confirmation."""
    query = update.callback_query
    await query.answer("Deleting...")
    tx_id = query.data.split('_')[-1]
    success = api_client.delete_transaction(tx_id)

    if success:
        await query.edit_message_text("🗑️ Transaction successfully deleted.")
        # Brief pause before showing the updated history
        import asyncio
        await asyncio.sleep(1.5)
        await history_menu(update, context)
    else:
        await query.edit_message_text("❌ Error: Could not delete transaction.",
                                      reply_markup=keyboards.manage_tx_keyboard(tx_id))


# --- START OF MODIFICATION ---

# --- Edit Transaction Conversation ---

async def _update_transaction_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper to perform the API call, confirm to user, and end conversation."""
    tx_id = context.user_data.get('edit_tx_id')
    field_to_edit = context.user_data.get('edit_tx_field')
    new_value = context.user_data.get('edit_tx_new_value')

    message_to_use = update.message or update.callback_query.message

    if not all([tx_id, field_to_edit, new_value is not None]):
        await context.bot.send_message(
            chat_id=message_to_use.chat_id,
            text="❌ An error occurred. Missing data to perform update. Please try again.",
            reply_markup=keyboards.main_menu_keyboard()
        )
        return ConversationHandler.END

    update_data = {field_to_edit: new_value}
    response = api_client.update_transaction(tx_id, update_data)

    if response and 'error' not in response:
        base_text = f"✅ Transaction successfully updated!"
        summary_data = api_client.get_detailed_summary()
        summary_text = format_summary_message(summary_data)
        await context.bot.send_message(
            chat_id=message_to_use.chat_id,
            text=base_text + summary_text,
            parse_mode='HTML',
            reply_markup=keyboards.main_menu_keyboard()
        )
    else:
        error_msg = response.get('error',
                                'Could not update transaction.') if response else 'Could not update transaction.'
        await context.bot.send_message(
            chat_id=message_to_use.chat_id,
            text=f"❌ Error: {error_msg}",
            reply_markup=keyboards.main_menu_keyboard()
        )

    context.user_data.clear()
    return ConversationHandler.END


@restricted
async def edit_transaction_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for the edit conversation. Shows fields that can be edited."""
    query = update.callback_query
    await query.answer()
    tx_id = query.data.split('_')[-1]

    # Store tx_id and fetch details to determine tx type (income/expense)
    context.user_data.clear()
    transaction = api_client.get_transaction_details(tx_id)
    if not transaction:
        await query.edit_message_text("❌ Error: Could not find transaction. It may have been deleted.",
                                      reply_markup=keyboards.main_menu_keyboard())
        return ConversationHandler.END

    context.user_data['edit_tx_id'] = tx_id
    context.user_data['edit_tx_type'] = transaction.get('type')  # Store for category keyboard

    await query.edit_message_text(
        "Which field would you like to edit?",
        reply_markup=keyboards.edit_tx_options_keyboard(tx_id)
    )
    return EDIT_CHOOSE_FIELD


async def edit_choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the user's choice of which field to edit."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split('_')
    field_to_edit = parts[2]

    context.user_data['edit_tx_field'] = field_to_edit

    if field_to_edit == 'categoryId':
        tx_type = context.user_data.get('edit_tx_type')
        keyboard = keyboards.income_categories_keyboard() if tx_type == 'income' else keyboards.expense_categories_keyboard()
        await query.edit_message_text("Please select the new category:", reply_markup=keyboard)
        return EDIT_GET_NEW_CATEGORY

    elif field_to_edit == 'amount':
        await query.edit_message_text("Please enter the new amount:")
        return EDIT_GET_NEW_VALUE

    elif field_to_edit == 'description':
        await query.edit_message_text("Please enter the new description:")
        return EDIT_GET_NEW_VALUE

    return ConversationHandler.END  # Fallback


async def edit_received_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives text input for the new amount or description."""
    field_to_edit = context.user_data.get('edit_tx_field')
    new_value_str = update.message.text

    if field_to_edit == 'amount':
        try:
            new_value = float(new_value_str)
            context.user_data['edit_tx_new_value'] = new_value
        except ValueError:
            await update.message.reply_text("Invalid amount. Please enter a valid number.")
            return EDIT_GET_NEW_VALUE
    else:  # Description
        context.user_data['edit_tx_new_value'] = new_value_str

    return await _update_transaction_and_confirm(update, context)


async def edit_received_new_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the new category from the keyboard callback."""
    query = update.callback_query
    await query.answer()

    new_category = query.data.split('_')[1]

    if new_category == 'other':
        # Custom category handling is complex for this flow, let's treat it as a string for now.
        await query.edit_message_text(
            "Editing to a custom category is not yet supported in this flow. Please choose a standard one.")
        tx_type = context.user_data.get('edit_tx_type')
        keyboard = keyboards.income_categories_keyboard() if tx_type == 'income' else keyboards.expense_categories_keyboard()
        await query.message.reply_markup(keyboard)
        return EDIT_GET_NEW_CATEGORY

    context.user_data['edit_tx_new_value'] = new_category
    return await _update_transaction_and_confirm(update, context)


# --- END OF MODIFICATION ---


# --- IOU / Debt Management ---
@restricted
async def iou_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the IOU management menu."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="🤝 Let's manage your IOUs.",
        reply_markup=keyboards.iou_menu_keyboard()
    )


@restricted
async def iou_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a summary list of all open debts, grouped by person."""
    query = update.callback_query
    await query.answer()
    grouped_debts = api_client.get_open_debts()

    text_to_send = "Here is a summary of debts by person.\nSelect one to see details:"
    reply_markup_to_send = keyboards.iou_list_keyboard(grouped_debts)

    if not grouped_debts:
        text_to_send = "You have no open debts! 👍"
        reply_markup_to_send = keyboards.iou_menu_keyboard()

    await query.edit_message_text(
        text=text_to_send,
        reply_markup=reply_markup_to_send
    )


@restricted
async def iou_person_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows all individual debts for a specific person and currency."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split(':')

    if len(parts) != 4:
        await query.edit_message_text(text="Error: Invalid or outdated button. Please go back and try again.",
                                      reply_markup=keyboards.iou_menu_keyboard())
        return

    _, _, person_name, currency = parts
    person_debts = api_client.get_debts_by_person_and_currency(person_name, currency)

    if not person_debts:
        await query.edit_message_text(text=f"❌ Could not find any open {currency} debts for {person_name}.",
                                      reply_markup=keyboards.iou_menu_keyboard())
        return

    total = sum(d['remainingAmount'] for d in person_debts)
    direction = "owes you" if person_debts[0]['type'] == 'lent' else "you owe"
    text = (
        f"<b>Debts for {person_name}</b> ({direction})\n"
        f"<b>Total Remaining:</b> {total:,.2f} {currency}\n\n"
        "Select a specific loan to view, or record a repayment:"
    )

    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.iou_person_detail_keyboard(person_debts, person_name, currency)
    )


@restricted
async def iou_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows details for a single debt, including the date."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split(':')

    if len(parts) != 5:
        await query.edit_message_text(text="Error: Invalid or outdated button. Please go back and try again.",
                                      reply_markup=keyboards.iou_menu_keyboard())
        return

    _, _, debt_id, person_name, currency = parts
    debt = api_client.get_debt_details(debt_id)
    if not debt:
        await query.edit_message_text(text="❌ Error: Could not find this debt.",
                                      reply_markup=keyboards.iou_menu_keyboard())
        return

    direction = "Owes you" if debt['type'] == 'lent' else "You owe"
    purpose_text = f"<b>Purpose:</b> {debt['purpose']}\n" if debt.get('purpose') else ""
    # Format timestamp to local time for display
    created_date_obj = datetime.fromisoformat(debt['created_at'].replace('Z', '+00:00'))
    created_date_str = created_date_obj.astimezone(PHNOM_PENH_TZ).strftime('%d %b %Y, %I:%M %p')
    date_text = f"<b>Date Created:</b> {created_date_str}\n"
    text = (
        f"<b>Debt Details:</b>\n"
        f"<b>Person:</b> {debt['person']} ({direction})\n"
        f"{date_text}"
        f"{purpose_text}"
        f"<b>Original Amount:</b> {debt.get('originalAmount', 0):,.2f} {debt.get('currency', '')}\n"
        f"<b>Remaining Balance:</b> {debt.get('remainingAmount', 0):,.2f} {debt.get('currency', '')}"
    )

    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.iou_detail_keyboard(debt_id, person_name, currency)
    )


# --- Lump-Sum Repayment Conversation ---
@restricted
async def repay_lump_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the lump-sum repayment conversation."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split(':')

    if len(parts) != 4:
        await query.edit_message_text(
            text="Error: Invalid or outdated button. Please go back and try again.",
            reply_markup=keyboards.iou_menu_keyboard())
        return ConversationHandler.END

    _, _, person_name, currency = parts
    context.user_data['lump_repay_person'] = person_name
    context.user_data['lump_repay_currency'] = currency

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"How much did {person_name} repay in {currency}?"
    )
    return REPAY_LUMP_AMOUNT


async def received_lump_repayment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and processes the lump-sum repayment amount."""
    try:
        amount = float(update.message.text)
        person = context.user_data['lump_repay_person']
        currency = context.user_data['lump_repay_currency']

        response = api_client.record_lump_sum_repayment(person, currency, amount)
        base_text = f"✅ {response['message']}" if 'error' not in response else f"❌ Error: {response['error']}"

        summary_data = api_client.get_detailed_summary()
        summary_text = format_summary_message(summary_data)

        await update.message.reply_text(
            base_text + summary_text,
            parse_mode='HTML',
            reply_markup=keyboards.main_menu_keyboard()
        )
    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid number for the repayment amount.")
        return REPAY_LUMP_AMOUNT

    context.user_data.clear()
    return ConversationHandler.END


# --- IOU Add Conversation ---
@restricted
async def iou_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the IOU conversation by asking for the date."""
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data['iou_type'] = 'lent' if query.data == 'iou_lent' else 'borrowed'
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="When did this happen?",
        reply_markup=keyboards.iou_date_keyboard()
    )
    return IOU_ASK_DATE


async def iou_received_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the date choice for an IOU."""
    query = update.callback_query
    await query.answer()
    choice = query.data

    prompt = "Who did you lend money to?" if context.user_data[
                                                 'iou_type'] == 'lent' else "Who did you borrow money from?"

    if choice == 'iou_date_today':
        await context.bot.send_message(chat_id=query.message.chat_id, text=prompt)
        return IOU_PERSON
    elif choice == 'iou_date_yesterday':
        local_today = datetime.now(PHNOM_PENH_TZ).date()
        local_yesterday = local_today - timedelta(days=1)
        aware_dt = datetime.combine(local_yesterday, time(12, 0), tzinfo=PHNOM_PENH_TZ)
        context.user_data['timestamp'] = aware_dt.isoformat()
        await context.bot.send_message(chat_id=query.message.chat_id, text=prompt)
        return IOU_PERSON
    elif choice == 'iou_date_custom':
        await context.bot.send_message(chat_id=query.message.chat_id,
                                       text="Please enter the date in YYYY-MM-DD format.")
        return IOU_CUSTOM_DATE


async def iou_received_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the custom date input for an IOU."""
    date_str = update.message.text
    try:
        custom_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        aware_dt = datetime.combine(custom_date, time(12, 0), tzinfo=PHNOM_PENH_TZ)
        context.user_data['timestamp'] = aware_dt.isoformat()

        prompt = "Who did you lend money to?" if context.user_data[
                                                     'iou_type'] == 'lent' else "Who did you borrow money from?"
        await update.message.reply_text(prompt)
        return IOU_PERSON
    except ValueError:
        await update.message.reply_text("Invalid format. Please use YYYY-MM-DD.")
        return IOU_CUSTOM_DATE


async def iou_received_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['iou_person'] = update.message.text
    await update.message.reply_text("How much?")
    return IOU_AMOUNT


async def iou_received_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['iou_amount'] = float(update.message.text)
        await update.message.reply_text("Which currency?", reply_markup=keyboards.currency_keyboard())
        return IOU_CURRENCY
    except ValueError:
        await update.message.reply_text("Please enter a valid number for the amount.")
        return IOU_AMOUNT


async def iou_received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the currency and asks for the purpose, confirming the choice."""
    query = update.callback_query
    await query.answer()
    currency = query.data.split('_')[1]
    context.user_data['iou_currency'] = currency

    text = f"Currency: <b>{currency}</b>\n\nWhat was this for? (e.g., Lunch, Deposit)"
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='HTML')
    return IOU_PURPOSE


async def iou_received_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the purpose and saves the new IOU."""
    context.user_data['iou_purpose'] = update.message.text
    debt_data = {
        "type": context.user_data['iou_type'],
        "person": context.user_data['iou_person'],
        "amount": context.user_data['iou_amount'],
        "currency": context.user_data['iou_currency'],
        "purpose": context.user_data['iou_purpose'],
        "timestamp": context.user_data.get('timestamp')
    }
    response = api_client.add_debt(debt_data)
    base_text = "✅ Debt successfully recorded!" if response else "❌ Failed to record debt."
    summary_data = api_client.get_detailed_summary()
    summary_text = format_summary_message(summary_data)
    await update.message.reply_text(
        base_text + summary_text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END


# --- Set Reminder Conversation ---
@restricted
async def set_reminder_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation to set a new reminder."""
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="What would you like to be reminded of?"
    )
    return REMINDER_PURPOSE


async def received_reminder_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the reminder purpose and asks for the date."""
    context.user_data['reminder_purpose'] = update.message.text
    await update.message.reply_text(
        "When should I remind you?",
        reply_markup=keyboards.reminder_date_keyboard()
    )
    return REMINDER_ASK_DATE


async def received_reminder_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the date choice for a reminder."""
    query = update.callback_query
    await query.answer()

    button_text = ""
    for row in query.message.reply_markup.inline_keyboard:
        for button in row:
            if button.callback_data == query.data:
                button_text = button.text.replace("🗓️ ", "")

    choice = query.data.split('_')[-1]

    if choice == 'custom':
        text = f"Date: <b>{button_text}</b>\n\nPlease enter the date in YYYY-MM-DD format."
        await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='HTML')
        return REMINDER_CUSTOM_DATE

    try:
        days = int(choice)
        local_today = datetime.now(PHNOM_PENH_TZ).date()
        reminder_date = local_today + timedelta(days=days)
        context.user_data['reminder_date_part'] = reminder_date
        text = f"Date: <b>{button_text}</b>\n\nGot it. And at what time? (e.g., 09:00, 17:30)"
        await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='HTML')
        return REMINDER_ASK_TIME
    except (ValueError, TypeError):
        await context.bot.send_message(chat_id=query.message.chat_id, text="Invalid choice. Please try again.")
        return REMINDER_ASK_DATE


async def received_reminder_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the custom date input for a reminder."""
    date_str = update.message.text
    try:
        custom_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        context.user_data['reminder_date_part'] = custom_date
        await update.message.reply_text("Got it. And at what time? (e.g., 09:00, 17:30)")
        return REMINDER_ASK_TIME
    except ValueError:
        await update.message.reply_text("Invalid format. Please use YYYY-MM-DD.")
        return REMINDER_CUSTOM_DATE


async def received_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the time, combines it with the date, and saves the reminder."""
    time_str = update.message.text
    try:
        reminder_time = datetime.strptime(time_str, "%H:%M").time()
        reminder_date = context.user_data['reminder_date_part']

        aware_reminder_dt = datetime.combine(reminder_date, reminder_time, tzinfo=PHNOM_PENH_TZ)
        context.user_data['reminder_datetime'] = aware_reminder_dt.isoformat()
        return await _save_reminder_and_confirm(update, context)
    except ValueError:
        await update.message.reply_text("Invalid time format. Please use HH:MM (24-hour format, e.g., 09:00 or 17:30).")
        return REMINDER_ASK_TIME


async def _save_reminder_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper function to save the reminder and end the conversation."""
    reminder_data = {
        "purpose": context.user_data['reminder_purpose'],
        "reminder_datetime": context.user_data['reminder_datetime'],
        "chat_id": update.effective_chat.id
    }
    response = api_client.add_reminder(reminder_data)

    message_to_use = update.message

    if response and 'error' not in response:
        reminder_date_obj = datetime.fromisoformat(context.user_data['reminder_datetime'])
        await message_to_use.reply_text(
            f"✅ Got it! I will remind you on {reminder_date_obj.astimezone(PHNOM_PENH_TZ).strftime('%d %b %Y at %H:%M')}.",
            reply_markup=keyboards.main_menu_keyboard()
        )
    else:
        error_msg = response.get('error', 'Please try again.') if response else 'Please try again.'
        await message_to_use.reply_text(
            f"❌ Sorry, I couldn't set that reminder. {error_msg}",
            reply_markup=keyboards.main_menu_keyboard()
        )

    context.user_data.clear()
    return ConversationHandler.END


# --- Set Initial Balance Conversation ---
@restricted
async def set_balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Which account do you want to set the balance for?",
        reply_markup=keyboards.set_balance_account_keyboard()
    )
    return SETBALANCE_ACCOUNT


async def received_balance_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    currency = query.data.split('_')[-1]
    context.user_data['currency'] = currency
    context.user_data['accountName'] = "USD Account" if currency == "USD" else "KHR Account"

    text = f"Account: <b>{currency}</b>\n\nWhat is the total current balance for your {currency} Account?"
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        parse_mode='HTML'
    )
    return SETBALANCE_AMOUNT


async def received_balance_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        tx_data = {
            "type": "income", "amount": amount,
            "currency": context.user_data['currency'],
            "accountName": context.user_data['accountName'],
            "categoryId": "Initial Balance",
            "description": "Starting balance set by user"
        }
        api_client.add_transaction(tx_data)
        base_text = f"✅ Initial balance of {amount:,.2f} {context.user_data['currency']} set successfully!"
        summary_data = api_client.get_detailed_summary()
        summary_text = format_summary_message(summary_data)
        await update.message.reply_text(
            base_text + summary_text,
            parse_mode='HTML',
            reply_markup=keyboards.main_menu_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid number for the balance.")
        return SETBALANCE_AMOUNT


# --- Forgot to Log Conversation ---
@restricted
async def forgot_log_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Which day did you forget to log?",
        reply_markup=keyboards.forgot_day_keyboard()
    )
    return FORGOT_DATE


async def received_forgot_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    button_text = ""
    for row in query.message.reply_markup.inline_keyboard:
        for button in row:
            if button.callback_data == query.data:
                button_text = button.text.replace("🗓️ ", "")

    choice = query.data.split('_')[-1]

    if choice == 'custom':
        text = f"Date: <b>{button_text}</b>\n\nPlease enter the date in YYYY-MM-DD format."
        await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='HTML')
        return FORGOT_CUSTOM_DATE

    days_ago = int(choice)
    local_today = datetime.now(PHNOM_PENH_TZ).date()
    forgotten_date = local_today - timedelta(days=days_ago)
    aware_dt = datetime.combine(forgotten_date, time(12, 0), tzinfo=PHNOM_PENH_TZ)
    context.user_data['timestamp'] = aware_dt.isoformat()

    text = f"Date: <b>{button_text}</b>\n\nGot it. Was it an expense or an income?"
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        parse_mode='HTML',
        reply_markup=keyboards.forgot_type_keyboard()
    )
    return FORGOT_TYPE


async def received_forgot_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_str = update.message.text
    try:
        custom_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        aware_dt = datetime.combine(custom_date, time(12, 0), tzinfo=PHNOM_PENH_TZ)
        context.user_data['timestamp'] = aware_dt.isoformat()
        await update.message.reply_text(
            "Got it. Was it an expense or an income?",
            reply_markup=keyboards.forgot_type_keyboard()
        )
        return FORGOT_TYPE
    except ValueError:
        await update.message.reply_text("Invalid format. Please use YYYY-MM-DD.")
        return FORGOT_CUSTOM_DATE


async def received_forgot_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    button_text = "Expense" if "expense" in query.data else "Income"
    context.user_data['type'] = query.data.split('_')[-1]

    text = f"Type: <b>{button_text}</b>\n\nEnter the amount:"
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='HTML')
    return AMOUNT


# --- Add Transaction Conversation (Shared Logic for Forgot Log and New Transaction) ---
@restricted
async def add_transaction_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()  # Clear context for new transaction
    context.user_data['type'] = 'expense' if query.data == 'add_expense' else 'income'
    emoji = "💸" if context.user_data['type'] == 'expense' else "💰"
    await context.bot.send_message(chat_id=query.message.chat_id, text=f"{emoji} Enter the amount:")
    return AMOUNT


async def received_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['amount'] = float(update.message.text)
        await update.message.reply_text("Which currency?", reply_markup=keyboards.currency_keyboard())
        return CURRENCY
    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return AMOUNT


async def received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    currency = query.data.split('_')[1]
    context.user_data['currency'] = currency
    context.user_data['accountName'] = "USD Account" if currency == "USD" else "KHR Account"

    keyboard = keyboards.income_categories_keyboard() if context.user_data.get(
        'type') == 'income' else keyboards.expense_categories_keyboard()
    text = f"Currency: <b>{currency}</b>\n\nWhich category?"
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='HTML', reply_markup=keyboard)
    return CATEGORY


async def received_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category_choice = query.data.split('_')[1]

    if category_choice == 'other':
        await context.bot.send_message(chat_id=query.message.chat_id,
                                       text="Please type your custom category name (e.g., Side Project, Freelance).")
        return CUSTOM_CATEGORY
    else:
        context.user_data['categoryId'] = category_choice
        text = f"Category: <b>{category_choice}</b>\n\nGreat. Would you like to add a remark/description?"
        await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='HTML',
                                       reply_markup=keyboards.ask_remark_keyboard())
        return ASK_REMARK


async def received_custom_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['categoryId'] = update.message.text
    await update.message.reply_text("Great. Would you like to add a remark/description?",
                                    reply_markup=keyboards.ask_remark_keyboard())
    return ASK_REMARK


async def ask_remark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split('_')[1]

    if choice == 'yes':
        button_text = "Add Remark"
        text = f"Selection: <b>{button_text}</b>\n\nPlease type your remark."
        await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='HTML')
        return REMARK
    else:
        context.user_data['description'] = ''
        button_text = "Skip"
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"Selection: <b>{button_text}</b>",
                                       parse_mode='HTML')
        return await save_transaction_and_end(update, context)


async def received_remark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    return await save_transaction_and_end(update, context)


async def save_transaction_and_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = api_client.add_transaction(context.user_data)
    message_to_use = update.callback_query.message if update.callback_query else update.message
    base_text = "✅ Transaction recorded successfully!" if response else "❌ Failed to record transaction."
    summary_data = api_client.get_detailed_summary()
    summary_text = format_summary_message(summary_data)

    await context.bot.send_message(
        chat_id=message_to_use.chat_id,
        text=base_text + summary_text,
        parse_mode='HTML',
        reply_markup=keyboards.main_menu_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END


@restricted
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any active conversation."""
    message = "Operation cancelled."
    keyboard = keyboards.main_menu_keyboard()
    chat_id = update.effective_chat.id
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text=message, reply_markup=keyboard)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=keyboard)
    else:
        await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=keyboard)

    context.user_data.clear()
    return ConversationHandler.END


# --- Build Conversation Handlers ---
tx_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(add_transaction_start, pattern='^(add_expense|add_income)$')],
    states={
        AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_amount)],
        CURRENCY: [CallbackQueryHandler(received_currency, pattern='^curr_')],
        CATEGORY: [CallbackQueryHandler(received_category, pattern='^cat_')],
        CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_custom_category)],
        ASK_REMARK: [CallbackQueryHandler(ask_remark, pattern='^remark_')],
        REMARK: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_remark)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

# --- START OF MODIFICATION ---
edit_tx_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(edit_transaction_start, pattern='^edit_tx_')],
    states={
        EDIT_CHOOSE_FIELD: [CallbackQueryHandler(edit_choose_field, pattern='^edit_field_')],
        EDIT_GET_NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_received_new_value)],
        EDIT_GET_NEW_CATEGORY: [CallbackQueryHandler(edit_received_new_category, pattern='^cat_')]
    },
    fallbacks=[
        CommandHandler('cancel', cancel),
        CommandHandler('start', start),
        CallbackQueryHandler(cancel, pattern='^cancel_conversation$')
    ],
    per_message=False
)
# --- END OF MODIFICATION ---

repay_lump_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(repay_lump_start, pattern='^iou:repay:')],
    states={
        REPAY_LUMP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_lump_repayment_amount)]
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

forgot_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(forgot_log_start, pattern='^forgot_log_start$')],
    states={
        FORGOT_DATE: [CallbackQueryHandler(received_forgot_day, pattern='^forgot_day_')],
        FORGOT_CUSTOM_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_forgot_custom_date)],
        FORGOT_TYPE: [CallbackQueryHandler(received_forgot_type, pattern='^forgot_type_')],
        AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_amount)],
        CURRENCY: [CallbackQueryHandler(received_currency, pattern='^curr_')],
        CATEGORY: [CallbackQueryHandler(received_category, pattern='^cat_')],
        CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_custom_category)],
        ASK_REMARK: [CallbackQueryHandler(ask_remark, pattern='^remark_')],
        REMARK: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_remark)],
    },
    fallbacks=[
        CommandHandler('cancel', cancel),
        CommandHandler('start', start),
        CallbackQueryHandler(cancel, pattern='^cancel_conversation$')
    ],
    per_message=False
)

rate_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(update_rate_start, pattern='^update_rate$')],
    states={NEW_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_new_rate)]},
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

iou_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(iou_start, pattern='^(iou_lent|iou_borrowed)$')],
    states={
        IOU_ASK_DATE: [CallbackQueryHandler(iou_received_date_choice, pattern='^iou_date_')],
        IOU_CUSTOM_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_custom_date)],
        IOU_PERSON: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_person)],
        IOU_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_amount)],
        IOU_CURRENCY: [CallbackQueryHandler(iou_received_currency, pattern='^curr_')],
        IOU_PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_purpose)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

set_balance_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(set_balance_start, pattern='^set_balance_start$')],
    states={
        SETBALANCE_ACCOUNT: [CallbackQueryHandler(received_balance_account, pattern='^set_balance_')],
        SETBALANCE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_balance_amount)]
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

reminder_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(set_reminder_start, pattern='^set_reminder_start$')],
    states={
        REMINDER_PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_reminder_purpose)],
        REMINDER_ASK_DATE: [CallbackQueryHandler(received_reminder_date_choice, pattern='^remind_date_')],
        REMINDER_CUSTOM_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_reminder_custom_date)],
        REMINDER_ASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_reminder_time)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

report_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(report_menu, pattern='^report_menu$')],
    states={
        CHOOSE_REPORT_PERIOD: [CallbackQueryHandler(process_report_choice, pattern='^report_period_')],
        REPORT_ASK_START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_report_start_date)],
        REPORT_ASK_END_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_report_end_date)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CallbackQueryHandler(start, pattern='^start$')],
    per_message=False
)
# --- End of modified file: telegram_bot/handlers.py ---