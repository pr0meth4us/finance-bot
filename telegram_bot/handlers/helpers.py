# --- Start of modified file: telegram_bot/handlers/helpers.py ---

from datetime import datetime
import io
import matplotlib.pyplot as plt
from zoneinfo import ZoneInfo # <-- NEW IMPORT

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh") # <-- NEW

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

    # --- Activity Periods (FIXED KHR FORMATTING) ---
    def format_period_line(period_data):
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
        this_month_net = periods.get('this_month', {}).get('net_usd', 0)
        net_emoji = '✅' if this_month_net >= 0 else '🔻'

        today_text = f"<b>Today:</b>\n{format_period_line(periods.get('today', {}))}"
        this_week_text = f"<b>This Week:</b>\n{format_period_line(periods.get('this_week', {}))}"
        last_week_text = f"<b>Last Week:</b>\n{format_period_line(periods.get('last_week', {}))}"
        this_month_text = f"<b>This Month:</b>\n{format_period_line(periods.get('this_month', {}))}"
        this_month_net_text = f"    <b>Net: ${this_month_net:,.2f}</b> {net_emoji}"

        activity_text = f"<b>Operational Activity (Excl. Loans):</b>\n{today_text}\n{this_week_text}\n{last_week_text}\n{this_month_text}\n{this_month_net_text}"

    return f"\n\n--- Your Current Status ---\n{balance_text}\n\n{debt_text}\n\n{activity_text}"


def format_summation_results(params, results):
    """ --- THIS FUNCTION HAS BEEN REWRITTEN --- """
    """Formats the results from the summation analytics API into a readable string."""
    if not results or results.get('total_count', 0) == 0:
        return "No transactions found matching your criteria."

    header = "<b>📈 Search Totals</b>\n\n"

    # 1. Build a summary of the query
    query_summary = []
    if params.get('period'):
        query_summary.append(f"<b>Period:</b> {params['period'].replace('_', ' ').title()}")
    elif params.get('start_date'):
        start = datetime.fromisoformat(params['start_date']).strftime('%b %d, %Y')
        end = datetime.fromisoformat(params['end_date']).strftime('%b %d, %Y')
        query_summary.append(f"<b>Period:</b> {start} to {end}")

    if params.get('transaction_type'):
        query_summary.append(f"<b>Type:</b> {params['transaction_type'].title()}")

    if params.get('categories'):
        query_summary.append(f"<b>Categories:</b> {', '.join(params['categories'])}")

    if params.get('keywords'):
        logic = params.get('keyword_logic', 'OR')
        query_summary.append(f"<b>Keywords:</b> {', '.join(params['keywords'])} (Logic: {logic})")

    header += "\n".join(query_summary) + "\n\n"

    # 2. Build Date Range
    date_text = ""
    if results.get('earliest_log_utc') and results.get('latest_log_utc'):
        earliest = datetime.fromisoformat(results['earliest_log_utc']).astimezone(PHNOM_PENH_TZ).strftime('%b %d, %Y')
        latest = datetime.fromisoformat(results['latest_log_utc']).astimezone(PHNOM_PENH_TZ).strftime('%b %d, %Y')
        if earliest == latest:
            date_text = f"<b>Date:</b> {earliest}\n"
        else:
            date_text = f"<b>Date Range:</b> {earliest} to {latest}\n"

    # 3. Build Totals & Stats
    total_count = results['total_count']
    count_text = f"Found <b>{total_count}</b> matching transaction(s).\n"

    stats_lines = []

    for item in results.get('totals_by_currency', []):
        currency = item['currency']
        amount_format = ",.0f" if currency == 'KHR' else ",.2f"
        symbol = "៛" if currency == 'KHR' else "💵"

        stats_lines.append(f"\n--- <b>Stats for {currency}</b> ---")
        stats_lines.append(f"  {symbol} <b>Total Sum:</b> {item['total']:{amount_format}} {currency}")
        stats_lines.append(f"  <b>Count:</b> {item['count']} transactions")
        stats_lines.append(f"  <b>Average:</b> {item['avg']:{amount_format}} {currency}")
        stats_lines.append(f"  <b>Highest:</b> {item['max']:{amount_format}} {currency}")
        stats_lines.append(f"  <b>Lowest:</b> {item['min']:{amount_format}} {currency}")

    return header + date_text + count_text + "\n".join(stats_lines)


def _format_report_summary_message(data):
    """Formats the detailed report data into a readable string."""
    summary = data.get('summary', {})
    start_date = datetime.fromisoformat(data['startDate']).strftime('%b %d, %Y')
    end_date = datetime.fromisoformat(data['endDate']).strftime('%b %d, %Y')

    start_balance = summary.get('balanceAtStartUSD', 0)
    end_balance = summary.get('balanceAtEndUSD', 0)

    header = f"📊 <b>Financial Report</b>\n🗓️ <i>{start_date} to {end_date}</i>\n\n"
    balance_overview_text = (
        f"<b>Balance Overview (in USD):</b>\n"
        f"▫️ Starting Balance: ${start_balance:,.2f}\n"
        f"▫️ Ending Balance: ${end_balance:,.2f}\n\n"
    )

    income = summary.get('totalIncomeUSD', 0)
    expense = summary.get('totalExpenseUSD', 0)
    net = summary.get('netSavingsUSD', 0)
    summary_text = (
        f"<b>Operational Summary (in USD):</b>\n"
        f"⬆️ Total Income: ${income:,.2f}\n"
        f"⬇️ Total Expense: ${expense:,.2f}\n"
        f"<b>Net Savings: ${net:,.2f}</b> {'✅' if net >= 0 else '🔻'}\n\n"
    )

    expense_breakdown = data.get('expenseBreakdown', [])
    major_expenses = []
    minor_expenses = []
    other_text = ""
    threshold = 4.0

    if expense > 0:
        for item in expense_breakdown:
            percentage = (item['totalUSD'] / expense) * 100
            if percentage < threshold:
                minor_expenses.append(item)
            else:
                major_expenses.append(item)

    expense_text = "<b>Major Expenses:</b>\n"
    if major_expenses:
        for item in major_expenses:
            expense_text += f"    - {item['category']}: ${item['totalUSD']:,.2f}\n"
    else:
        expense_text += "    - No major expenses recorded.\n"

    if minor_expenses:
        other_text = "\n<b>Other Expenses (grouped in chart):</b>\n"
        for item in minor_expenses:
            other_text += f"    - {item['category']}: ${item['totalUSD']:,.2f}\n"

    income_breakdown = data.get('incomeBreakdown', [])
    income_text = "\n<b>Income Sources:</b>\n"
    if income_breakdown:
        for item in income_breakdown[:5]:
            income_text += f"    - {item['category']}: ${item['totalUSD']:,.2f}\n"
    else:
        "    - No income recorded.\n"

    fin_summary = data.get('financialSummary', {})
    financial_text = "\n<b>Loan & Debt Activity (in USD):</b>\n"
    financial_lines = [
        f"    - Lent to others: ${fin_summary['totalLentUSD']:,.2f}" if fin_summary.get('totalLentUSD',
                                                                                        0) > 0 else None,
        f"    - Borrowed from others: ${fin_summary['totalBorrowedUSD']:,.2f}" if fin_summary.get('totalBorrowedUSD',
                                                                                                  0) > 0 else None,
        f"    - Repayments received: ${fin_summary['totalRepaidToYouUSD']:,.2f}" if fin_summary.get(
            'totalRepaidToYouUSD', 0) > 0 else None,
        f"    - Repayments made: ${fin_summary['totalYouRepaidUSD']:,.2f}" if fin_summary.get('totalYouRepaidUSD',
                                                                                              0) > 0 else None
    ]
    active_lines = [line for line in financial_lines if line]
    financial_text += "\n".join(active_lines) if active_lines else "    - No loan or debt activity."

    return header + balance_overview_text + summary_text + expense_text + other_text + income_text + financial_text


def _create_income_expense_chart(data, start_date, end_date):
    """Creates a simple bar chart comparing income and expense."""
    summary = data.get('summary', {})
    income = summary.get('totalIncomeUSD', 0)
    expense = summary.get('totalExpenseUSD', 0)
    if income == 0 and expense == 0:
        return None

    date_range_str = f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}"

    labels = ['Income', 'Expense']
    values = [income, expense]
    colors = ['#4CAF50', '#F44336']
    fig, ax = plt.subplots(figsize=(6, 5))

    ax.set_title('Operational Income vs. Expense', pad=20)
    plt.suptitle(date_range_str, y=0.93, fontsize=10)

    bars = ax.bar(labels, values, color=colors)
    ax.set_ylabel('Amount (USD)')
    ax.spines[['top', 'right']].set_visible(False)

    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2.0, yval, f'${yval:,.2f}', va='bottom', ha='center')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _create_expense_pie_chart(data, start_date, end_date):
    """Creates a pie chart for the expense breakdown."""
    expense_breakdown = data.get('expenseBreakdown', [])
    total_expense = data.get('summary', {}).get('totalExpenseUSD', 0)
    if not expense_breakdown or total_expense == 0:
        return None

    threshold = 4.0
    new_labels = []
    new_sizes = []
    other_total = 0

    if total_expense > 0:
        for item in expense_breakdown:
            percentage = (item['totalUSD'] / total_expense) * 100
            if percentage < threshold:
                other_total += item['totalUSD']
            else:
                new_labels.append(item['category'])
                new_sizes.append(item['totalUSD'])

    if other_total > 0:
        new_labels.append('Other')
        new_sizes.append(other_total)

    labels = new_labels
    sizes = new_sizes

    date_range_str = f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}"

    explode = [0] * len(labels)
    if sizes:
        explode[sizes.index(max(sizes))] = 0.05

    fig, ax = plt.subplots(figsize=(7, 6))

    ax.set_title('Expense Breakdown', pad=20)
    plt.suptitle(date_range_str, y=0.93, fontsize=10)

    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, pctdistance=0.85, explode=explode)
    ax.axis('equal')
    fig.gca().add_artist(plt.Circle((0, 0), 0.70, fc='white'))

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _format_habits_message(data):
    """Formats the spending habits data into a readable string."""
    if not data:
        return "Could not analyze spending habits."

    day_text = "\n<b>📅 Spending by Day of Week:</b>\n"
    by_day = sorted(data.get('byDayOfWeek', []), key=lambda x: x.get('total', 0), reverse=True)
    day_text += "\n".join(
        [f"    - {item['day']}s: ${item['total']:,.2f}" for item in by_day]) or "    - Not enough data.\n"

    keyword_text = "\n<b>🏷️ Common Spending Keywords:</b>\n"
    by_keyword = data.get('keywordsByCategory', [])
    if by_keyword:
        for item in by_keyword:
            if item.get('topKeywords'):
                keywords = ", ".join(item['topKeywords'])
                keyword_text += f"    - <b>{item['category']}:</b> {keywords}\n"
    else:
        keyword_text += "    - No descriptions found to analyze.\n"

    return day_text + keyword_text