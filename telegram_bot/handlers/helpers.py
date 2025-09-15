# --- Start of modified file: telegram_bot/handlers/helpers.py ---

from datetime import datetime
import io
import matplotlib.pyplot as plt


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
        today_text = f"<b>Today:</b>\n{format_period_line(periods.get('today', {}))}"
        this_week_text = f"<b>This Week:</b>\n{format_period_line(periods.get('this_week', {}))}"
        this_month_text = f"<b>This Month:</b>\n{format_period_line(periods.get('this_month', {}))}"
        activity_text = f"<b>Operational Activity (Excl. Loans):</b>\n{today_text}\n{this_week_text}\n{this_month_text}"

    return f"\n\n--- Your Current Status ---\n{balance_text}\n\n{debt_text}\n\n{activity_text}"


def _format_report_summary_message(data):
    """Formats the detailed report data into a readable string."""
    summary = data.get('summary', {})
    start_date = datetime.fromisoformat(data['startDate']).strftime('%b %d, %Y')
    end_date = datetime.fromisoformat(data['endDate']).strftime('%b %d, %Y')

    # --- START OF MODIFICATION: New Balance Overview Section ---
    start_balance = summary.get('balanceAtStartUSD', 0)
    end_balance = summary.get('balanceAtEndUSD', 0)

    header = f"📊 <b>Financial Report</b>\n🗓️ <i>{start_date} to {end_date}</i>\n\n"
    balance_overview_text = (
        f"<b>Balance Overview (in USD):</b>\n"
        f"▫️ Starting Balance: ${start_balance:,.2f}\n"
        f"▫️ Ending Balance: ${end_balance:,.2f}\n\n"
    )
    # --- END OF MODIFICATION ---

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
    expense_text = "<b>Top Expenses:</b>\n"
    if expense_breakdown:
        for item in expense_breakdown[:5]:
            expense_text += f"    - {item['category']}: ${item['totalUSD']:,.2f}\n"
    else:
        expense_text += "    - No expenses recorded.\n"

    income_breakdown = data.get('incomeBreakdown', [])
    income_text = "\n<b>Income Sources:</b>\n"
    if income_breakdown:
        for item in income_breakdown[:5]:
            income_text += f"    - {item['category']}: ${item['totalUSD']:,.2f}\n"
    else:
        income_text += "    - No income recorded.\n"

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

    return header + balance_overview_text + summary_text + expense_text + income_text + financial_text


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

    # --- MODIFICATION ---
    ax.set_title('Operational Income vs. Expense', pad=20)  # Add padding for subtitle
    plt.suptitle(date_range_str, y=0.93, fontsize=10)  # Add subtitle with date range

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
    if not expense_breakdown or data.get('summary', {}).get('totalExpenseUSD', 0) == 0:
        return None

    date_range_str = f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}"

    labels = [item['category'] for item in expense_breakdown]
    sizes = [item['totalUSD'] for item in expense_breakdown]
    explode = [0] * len(labels)
    if sizes:
        explode[sizes.index(max(sizes))] = 0.05

    fig, ax = plt.subplots(figsize=(7, 6))

    # --- MODIFICATION ---
    ax.set_title('Expense Breakdown', pad=20)  # Add padding for subtitle
    plt.suptitle(date_range_str, y=0.93, fontsize=10)  # Add subtitle with date range

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
    time_text = "<b>🕒 Spending by Time of Day:</b>\n"
    by_time = sorted(data.get('byTimeOfDay', []), key=lambda x: x.get('total', 0), reverse=True)
    time_text += "\n".join(
        [f"    - {item['period']}: ${item['total']:,.2f}" for item in by_time]) or "    - Not enough data.\n"

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

    return time_text + day_text + keyword_text