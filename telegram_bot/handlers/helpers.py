# --- Start of modified file: telegram_bot/handlers/helpers.py ---

from datetime import datetime
import io
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from zoneinfo import ZoneInfo
import pandas as pd
from telegram.ext import ContextTypes
from ..utils.i18n import t

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")


def format_summary_message(summary_data,
                           context: ContextTypes.DEFAULT_TYPE):
    """Formats the detailed summary data into a readable string."""
    if not summary_data:
        return ""

    # Balances
    khr_bal = summary_data.get('balances', {}).get('KHR', 0)
    usd_bal = summary_data.get('balances', {}).get('USD', 0)
    balance_text = (
        f"{t('summary.balances', context)}\n"
        f"💵 {usd_bal:,.2f} USD\n៛ {khr_bal:,.0f} KHR"
    )

    # Debts
    owed_to_you_data = summary_data.get('debts_owed_to_you', [])
    owed_to_you_usd = next((item['total'] for item in owed_to_you_data
                            if item['_id'] == 'USD'), 0)
    owed_to_you_khr = next((item['total'] for item in owed_to_you_data
                            if item['_id'] == 'KHR'), 0)
    owed_to_you_text = (
        f"    💵 {owed_to_you_usd:,.2f} USD\n"
        f"    ៛ {owed_to_you_khr:,.0f} KHR"
    )

    owed_by_you_data = summary_data.get('debts_owed_by_you', [])
    owed_by_you_usd = next((item['total'] for item in owed_by_you_data
                            if item['_id'] == 'USD'), 0)
    owed_by_you_khr = next((item['total'] for item in owed_by_you_data
                            if item['_id'] == 'KHR'), 0)
    owed_by_you_text = (
        f"    💵 {owed_by_you_usd:,.2f} USD\n"
        f"    ៛ {owed_by_you_khr:,.0f} KHR"
    )

    debt_text = (
        f"{t('summary.debts', context)}\n"
        f"{t('summary.you_are_owed', context)}\n{owed_to_you_text}\n"
        f"{t('summary.you_owe', context)}\n{owed_by_you_text}"
    )

    # Activity Periods
    def format_period_line(period_data):
        income = period_data.get('income', {})
        expense = period_data.get('expense', {})

        income_parts = []
        if income.get('USD', 0) > 0:
            income_parts.append(f"{income['USD']:,.2f} USD")
        if income.get('KHR', 0) > 0:
            income_parts.append(f"{income['KHR']:,.0f} KHR")
        income_str = ' & '.join(income_parts) if income_parts else "0"

        expense_parts = []
        if expense.get('USD', 0) > 0:
            expense_parts.append(f"{expense['USD']:,.2f} USD")
        if expense.get('KHR', 0) > 0:
            expense_parts.append(f"{expense['KHR']:,.0f} KHR")
        expense_str = ' & '.join(expense_parts) if expense_parts else "0"

        return (
            f"{t('summary.in', context, value=income_str)}\n"
            f"{t('summary.out', context, value=expense_str)}"
        )

    periods = summary_data.get('periods', {})
    activity_text = ""
    if periods:
        this_month_net = periods.get('this_month', {}).get('net_usd', 0)
        net_emoji = '✅' if this_month_net >= 0 else '🔻'

        today_text = (
            f"{t('summary.today', context)}\n"
            f"{format_period_line(periods.get('today', {}))}"
        )
        this_week_text = (
            f"{t('summary.this_week', context)}\n"
            f"{format_period_line(periods.get('this_week', {}))}"
        )
        last_week_text = (
            f"{t('summary.last_week', context)}\n"
            f"{format_period_line(periods.get('last_week', {}))}"
        )
        this_month_text = (
            f"{t('summary.this_month', context)}\n"
            f"{format_period_line(periods.get('this_month', {}))}"
        )
        this_month_net_text = t(
            'summary.net',
            context,
            value=this_month_net,
            emoji=net_emoji
        )

        activity_text = (
            f"{t('summary.activity_header', context)}\n{today_text}\n"
            f"{this_week_text}\n{last_week_text}\n{this_month_text}\n"
            f"{this_month_net_text}"
        )

    return (
        f"{t('summary.status_header', context)}\n{balance_text}\n"
        f"\n{debt_text}\n\n{activity_text}"
    )


def format_summation_results(params, results,
                             context: ContextTypes.DEFAULT_TYPE):
    """Formats the results from the summation analytics API."""
    if not results or results.get('total_count', 0) == 0:
        return t('search.no_results', context)

    header = "<b>📈 Search Totals</b>\n\n"

    query_summary = []
    if params.get('period'):
        query_summary.append(
            f"<b>Period:</b> {params['period'].replace('_', ' ').title()}"
        )
    elif params.get('start_date'):
        start = datetime.fromisoformat(params['start_date'])
        end = datetime.fromisoformat(params['end_date'])
        query_summary.append(
            f"<b>Period:</b> {start:%b %d, %Y} to {end:%b %d, %Y}"
        )

    if params.get('transaction_type'):
        query_summary.append(
            f"<b>Type:</b> {params['transaction_type'].title()}"
        )

    if params.get('categories'):
        query_summary.append(
            f"<b>Categories:</b> {', '.join(params['categories'])}"
        )

    if params.get('keywords'):
        logic = params.get('keyword_logic', 'OR')
        query_summary.append(
            f"<b>Keywords:</b> {', '.join(params['keywords'])} "
            f"(Logic: {logic})"
        )

    header += "\n".join(query_summary) + "\n\n"

    # Date Range
    date_text = ""
    if results.get('earliest_log_utc') and results.get('latest_log_utc'):
        earliest = (
            datetime.fromisoformat(results['earliest_log_utc'])
            .astimezone(PHNOM_PENH_TZ)
            .strftime('%b %d, %Y')
        )
        latest = (
            datetime.fromisoformat(results['latest_log_utc'])
            .astimezone(PHNOM_PENH_TZ)
            .strftime('%b %d, %Y')
        )
        if earliest == latest:
            date_text = f"<b>Date:</b> {earliest}\n"
        else:
            date_text = f"<b>Date Range:</b> {earliest} to {latest}\n"

    # Totals & Stats
    total_count = results['total_count']
    count_text = f"Found <b>{total_count}</b> matching transaction(s).\n"

    stats_lines = []
    for item in results.get('totals_by_currency', []):
        currency = item['currency']
        amount_format = ",.0f" if currency == 'KHR' else ",.2f"
        symbol = "៛" if currency == 'KHR' else "💵"

        stats_lines.append(f"\n--- <b>Stats for {currency}</b> ---")
        stats_lines.append(
            f"  {symbol} <b>Total Sum:</b> {item['total']:{amount_format}} "
            f"{currency}"
        )
        stats_lines.append(f"  <b>Count:</b> {item['count']} transactions")
        stats_lines.append(
            f"  <b>Average:</b> {item['avg']:{amount_format}} {currency}"
        )
        stats_lines.append(
            f"  <b>Highest:</b> {item['max']:{amount_format}} {currency}"
        )
        stats_lines.append(
            f"  <b>Lowest:</b> {item['min']:{amount_format}} {currency}"
        )

    return header + date_text + count_text + "\n".join(stats_lines)


def _format_report_summary_message(data):
    """Formats the detailed report data into a readable string."""
    summary = data.get('summary', {})
    start_date = datetime.fromisoformat(data['startDate']).strftime('%b %d, %Y')
    end_date = datetime.fromisoformat(data['endDate']).strftime('%b %d, %Y')

    start_balance = summary.get('balanceAtStartUSD', 0)
    end_balance = summary.get('balanceAtEndUSD', 0)

    header = f"📊 <b>Financial Report</b>\n" \
             f"🗓️ <i>{start_date} to {end_date}</i>\n\n"
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

    insights = data.get('expenseInsights', {})
    insights_text = "<b>Expense Insights:</b>\n"

    top_item = insights.get('topExpenseItem')
    if top_item:
        top_desc = top_item.get('description') or top_item.get('category', 'N/A')
        insights_text += (
            f"    - <b>Top Expense:</b> ${top_item['amount_usd']:,.2f} "
            f"({top_desc}) on {top_item['date']}\n"
        )

    most_day = insights.get('mostExpensiveDay')
    if most_day:
        insights_text += (
            f"    - <b>Busiest Day:</b> {most_day['_id']} "
            f"(${most_day['total_spent_usd']:,.2f})\n"
        )

    least_day = insights.get('leastExpensiveDay')
    if least_day and (not most_day or least_day['_id'] != most_day['_id']):
        insights_text += (
            f"    - <b>Quietest Day:</b> {least_day['_id']} "
            f"(${least_day['total_spent_usd']:,.2f})\n"
        )

    insights_text += "\n"

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
            expense_text += (
                f"    - {item['category']}: ${item['totalUSD']:,.2f}\n"
            )
    else:
        expense_text += "    - No major expenses recorded.\n"

    if minor_expenses:
        other_text = "\n<b>Other Expenses (grouped in chart):</b>\n"
        for item in minor_expenses:
            other_text += (
                f"    - {item['category']}: ${item['totalUSD']:,.2f}\n"
            )

    income_breakdown = data.get('incomeBreakdown', [])
    income_text = "\n<b>Income Sources:</b>\n"
    if income_breakdown:
        for item in income_breakdown[:5]:
            income_text += (
                f"    - {item['category']}: ${item['totalUSD']:,.2f}\n"
            )
    else:
        income_text += "    - No income recorded.\n"

    fin_summary = data.get('financialSummary', {})
    financial_text = "\n<b>Loan & Debt Activity (in USD):</b>\n"
    financial_lines = [
        f"    - Lent to others: ${fin_summary['totalLentUSD']:,.2f}"
        if fin_summary.get('totalLentUSD', 0) > 0 else None,
        f"    - Borrowed from others: ${fin_summary['totalBorrowedUSD']:,.2f}"
        if fin_summary.get('totalBorrowedUSD', 0) > 0 else None,
        f"    - Repayments received: ${fin_summary['totalRepaidToYouUSD']:,.2f}"
        if fin_summary.get('totalRepaidToYouUSD', 0) > 0 else None,
        f"    - Repayments made: ${fin_summary['totalYouRepaidUSD']:,.2f}"
        if fin_summary.get('totalYouRepaidUSD', 0) > 0 else None
    ]
    active_lines = [line for line in financial_lines if line]
    financial_text += "\n".join(
        active_lines
    ) if active_lines else "    - No loan or debt activity."
    return (
            header + balance_overview_text + summary_text + insights_text +
            expense_text + other_text + income_text + financial_text
    )


def _create_income_expense_chart(data, start_date, end_date):
    """Creates a simple bar chart comparing income and expense."""
    summary = data.get('summary', {})
    income = summary.get('totalIncomeUSD', 0)
    expense = summary.get('totalExpenseUSD', 0)
    if income == 0 and expense == 0:
        return None

    date_range_str = f"{start_date.strftime('%b %d, %Y')} to " \
                     f"{end_date.strftime('%b %d, %Y')}"

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
        plt.text(bar.get_x() + bar.get_width() / 2.0, yval,
                 f'${yval:,.2f}', va='bottom', ha='center')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _create_spending_line_chart(data, start_date, end_date):
    """Creates a line chart for spending over time."""
    spending_data = data.get('spendingOverTime', [])
    if not spending_data:
        return None

    df = pd.DataFrame(spending_data)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')

    full_date_range = pd.date_range(start=start_date, end=end_date)
    df = df.reindex(full_date_range, fill_value=0)

    if df['total_spent_usd'].sum() == 0:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df.index, df['total_spent_usd'],
            marker='o', linestyle='-', markersize=4)
    ax.fill_between(df.index, df['total_spent_usd'], color='skyblue', alpha=0.3)

    date_range_str = f"{start_date.strftime('%b %d, %Y')} to " \
                     f"{end_date.strftime('%b %d, %Y')}"
    ax.set_title('Spending Over Time (USD)', pad=20)
    plt.suptitle(date_range_str, y=0.93, fontsize=10)
    ax.set_ylabel('Amount Spent (USD)')
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    num_days = len(df)
    if num_days <= 10:
        date_fmt = mdates.DateFormatter('%b %d')
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    elif num_days <= 90:
        date_fmt = mdates.DateFormatter('%b %d')
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1,
                                                         byweekday=mdates.MO))
    else:
        date_fmt = mdates.DateFormatter('%b %Y')
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))

    ax.xaxis.set_major_formatter(date_fmt)
    fig.autofmt_xdate()

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

    date_range_str = f"{start_date.strftime('%b %d, %Y')} to " \
                     f"{end_date.strftime('%b %d, %Y')}"

    explode = [0] * len(labels)
    if sizes:
        explode[sizes.index(max(sizes))] = 0.05

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.set_title('Expense Breakdown', pad=20)
    plt.suptitle(date_range_str, y=0.93, fontsize=10)

    ax.pie(sizes, labels=labels, autopct='%1.1f%%',
           startangle=90, pctdistance=0.85, explode=explode)
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
    by_day = sorted(data.get('byDayOfWeek', []),
                    key=lambda x: x.get('total', 0), reverse=True)
    day_text += "\n".join([
        f"    - {item['day']}s: ${item['total']:,.2f}" for item in by_day
    ]) or "    - Not enough data.\n"

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


def _format_debt_analysis_message(analysis_data,
                                  context: ContextTypes.DEFAULT_TYPE):
    """Formats the text summary for the debt analysis."""
    lent_by = [d for d in analysis_data.get('concentration', [])
               if d['type'] == 'lent']
    borrow_from = [d for d in analysis_data.get('concentration', [])
                   if d['type'] == 'borrowed']

    lent_text = t('iou.analysis_lent_header', context)
    lent_text += "\n".join([
        t('iou.analysis_item', context,
          person=item['person'], total=item['total'])
        for item in lent_by[:3]
    ]) or t('iou.analysis_lent_none', context)

    borrow_text = t('iou.analysis_borrow_header', context)
    borrow_text += "\n".join([
        t('iou.analysis_item', context,
          person=item['person'], total=item['total'])
        for item in borrow_from[:3]
    ]) or t('iou.analysis_borrow_none', context)

    aging_text = t('iou.analysis_aging_header', context)
    aging_data = analysis_data.get('aging', [])
    aging_text += "\n".join([
        t('iou.analysis_aging_item', context,
          person=item['_id'], days=item['averageAgeDays'],
          count=item['count'])
        for item in aging_data[:3]
    ]) or t('iou.analysis_aging_none', context)

    return (
        f"{t('iou.analysis_header', context)}\n"
        f"{lent_text}\n{borrow_text}\n{aging_text}"
    )


def _create_debt_overview_pie(analysis_data):
    """Creates a pie chart for total owed vs. total lent in USD."""
    overview = analysis_data.get('overview_usd', {})
    lent_usd = overview.get('total_lent_usd', 0)
    borrowed_usd = overview.get('total_borrowed_usd', 0)

    if lent_usd == 0 and borrowed_usd == 0:
        return None

    labels = ['You Are Owed', 'You Owe']
    sizes = [lent_usd, borrowed_usd]
    colors = ['#4CAF50', '#F44336']
    explode = (0.05, 0)

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.set_title('Debt Overview (USD Equivalent)', pad=20)

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct=lambda p: f'${p * sum(sizes) / 100:,.2f}\n({p:.1f}%)',
        startangle=90,
        pctdistance=0.75,
        explode=explode,
        colors=colors
    )
    plt.setp(autotexts, size=10, weight="bold", color="white")
    ax.axis('equal')
    fig.gca().add_artist(plt.Circle((0, 0), 0.60, fc='white'))

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _create_debt_concentration_bar(analysis_data):
    """Creates a horizontal bar chart for debt concentration by person."""
    concentration = analysis_data.get('concentration', [])
    if not concentration:
        return None

    lent_data = sorted(
        [d for d in concentration if d['type'] == 'lent'],
        key=lambda x: x['total'], reverse=True
    )[:5]
    borrow_data = sorted(
        [d for d in concentration if d['type'] == 'borrowed'],
        key=lambda x: x['total'], reverse=True
    )[:5]

    if not lent_data and not borrow_data:
        return None

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6), sharey=False)

    # Plot 1: You Are Owed (Lent)
    if lent_data:
        people_lent = [d['person'] for d in lent_data]
        amounts_lent = [d['total'] for d in lent_data]
        ax1.barh(people_lent, amounts_lent, color='#4CAF50')
        ax1.set_title('You Are Owed (Top 5)')
        ax1.set_xlabel('Amount (USD Equivalent)')
        ax1.invert_yaxis()
        for i, v in enumerate(amounts_lent):
            ax1.text(v + 1, i, f' ${v:,.2f}', va='center', color='black')
    else:
        ax1.set_title('You Are Owed')
        ax1.text(0.5, 0.5, 'No data',
                 horizontalalignment='center', verticalalignment='center',
                 transform=ax1.transAxes)
    ax1.spines[['top', 'right']].set_visible(False)

    # Plot 2: You Owe (Borrowed)
    if borrow_data:
        people_borrow = [d['person'] for d in borrow_data]
        amounts_borrow = [d['total'] for d in borrow_data]
        ax2.barh(people_borrow, amounts_borrow, color='#F44336')
        ax2.set_title('You Owe (Top 5)')
        ax2.set_xlabel('Amount (USD Equivalent)')
        ax2.invert_yaxis()
        for i, v in enumerate(amounts_borrow):
            ax2.text(v + 1, i, f' ${v:,.2f}', va='center', color='black')
    else:
        ax2.set_title('You Owe')
        ax2.text(0.5, 0.5, 'No data',
                 horizontalalignment='center', verticalalignment='center',
                 transform=ax2.transAxes)
    ax2.spines[['top', 'right']].set_visible(False)

    plt.suptitle('Debt Concentration', fontsize=16, y=1.02)
    plt.tight_layout(pad=2.0)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

# --- End of modified file ---