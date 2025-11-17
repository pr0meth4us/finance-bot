import io
import csv
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram.ext import ContextTypes
from utils.i18n import t

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")


def _get_user_settings(context: ContextTypes.DEFAULT_TYPE):
    """Extracts currency mode and currencies from context."""
    profile = context.user_data.get('profile', {})
    settings = profile.get('settings', {})
    mode = settings.get('currency_mode', 'dual')

    if mode == 'single':
        primary = settings.get('primary_currency', 'USD')
        return mode, (primary,)

    return 'dual', ('USD', 'KHR')


def format_summary_message(summary_data, context: ContextTypes.DEFAULT_TYPE):
    """Formats detailed summary data into a readable string."""
    if not summary_data:
        return ""

    mode, currencies = _get_user_settings(context)
    balances = summary_data.get('balances', {})

    # 1. Balances
    balance_lines = [f"{t('summary.balances', context)}"]
    if mode == 'dual':
        balance_lines.append(f"💵 {balances.get('USD', 0):,.2f} USD")
        balance_lines.append(f"៛ {balances.get('KHR', 0):,.0f} KHR")
    else:
        curr = currencies[0]
        val = balances.get(curr, 0)
        fmt = ",.0f" if curr == 'KHR' else ",.2f"
        balance_lines.append(f"<b>{val:{fmt}} {curr}</b>")

    # 2. Debts
    debt_lines = [f"{t('summary.debts', context)}"]

    def _format_debts(title, data):
        lines = [title]
        found = False
        for curr in currencies:
            total = next((i['total'] for i in data if i['_id'] == curr), 0)
            if total > 0:
                fmt = ",.0f" if curr == 'KHR' else ",.2f"
                symbol = "៛" if curr == 'KHR' else "💵"
                lines.append(f"    {symbol} {total:{fmt}} {curr}")
                found = True
        if not found:
            lines.append("    -")
        return lines

    debt_lines.extend(_format_debts(t('summary.you_are_owed', context), summary_data.get('debts_owed_to_you', [])))
    debt_lines.extend(_format_debts(t('summary.you_owe', context), summary_data.get('debts_owed_by_you', [])))

    # 3. Activity
    periods = summary_data.get('periods', {})
    activity_lines = [f"{t('summary.activity_header', context)}"]

    def _fmt_period(period_key, label_key):
        p_data = periods.get(period_key, {})
        inc = p_data.get('income', {})
        exp = p_data.get('expense', {})

        inc_str = " & ".join(
            [f"{inc.get(c, 0):{',.0f' if c == 'KHR' else ',.2f'}} {c}" for c in currencies if inc.get(c, 0) > 0]) or "0"
        exp_str = " & ".join(
            [f"{exp.get(c, 0):{',.0f' if c == 'KHR' else ',.2f'}} {c}" for c in currencies if exp.get(c, 0) > 0]) or "0"

        return f"{t(label_key, context)}\n{t('summary.in', context, value=inc_str)}\n{t('summary.out', context, value=exp_str)}"

    if periods:
        activity_lines.append(_fmt_period('today', 'summary.today'))
        activity_lines.append(_fmt_period('this_week', 'summary.this_week'))
        activity_lines.append(_fmt_period('last_week', 'summary.last_week'))
        activity_lines.append(_fmt_period('this_month', 'summary.this_month'))

        if mode == 'dual':
            net = periods.get('this_month', {}).get('net_usd', 0)
            emoji = '✅' if net >= 0 else '🔻'
            activity_lines.append(f"\n{t('summary.net', context, value=net, emoji=emoji)}")

    return "\n".join(balance_lines + [""] + debt_lines + [""] + activity_lines)


def format_summation_results(params, results, context: ContextTypes.DEFAULT_TYPE):
    """Formats summation analytics results."""
    if not results or results.get('total_count', 0) == 0:
        return t('search.no_results', context)

    header = "<b>📈 Search Totals</b>\n\n"
    meta = []

    if params.get('start_date'):
        s = datetime.fromisoformat(params['start_date'])
        e = datetime.fromisoformat(params['end_date'])
        meta.append(f"<b>Period:</b> {s:%b %d, %Y} to {e:%b %d, %Y}")

    if params.get('transaction_type'):
        meta.append(f"<b>Type:</b> {params['transaction_type'].title()}")

    if params.get('categories'):
        meta.append(f"<b>Categories:</b> {', '.join(params['categories'])}")

    stats = []
    for item in results.get('totals_by_currency', []):
        c = item['currency']
        fmt = ",.0f" if c == 'KHR' else ",.2f"
        sym = "៛" if c == 'KHR' else "💵"

        stats.append(
            f"\n--- <b>Stats for {c}</b> ---\n"
            f"  {sym} <b>Total:</b> {item['total']:{fmt}} {c}\n"
            f"  <b>Count:</b> {item['count']}\n"
            f"  <b>Avg:</b> {item['avg']:{fmt}} {c}\n"
            f"  <b>Max:</b> {item['max']:{fmt}} {c}"
        )

    return header + "\n".join(meta) + "\n".join(stats)


def _format_report_summary_message(data, context: ContextTypes.DEFAULT_TYPE):
    s = data.get('summary', {})
    start = datetime.fromisoformat(data['startDate']).strftime('%b %d, %Y')
    end = datetime.fromisoformat(data['endDate']).strftime('%b %d, %Y')

    header = t("analytics.report_header", context, start_date=start, end_date=end)

    balance = (
            t("analytics.balance_overview", context) +
            t("analytics.starting_balance", context, balance=s.get('balanceAtStartUSD', 0)) +
            t("analytics.ending_balance", context, balance=s.get('balanceAtEndUSD', 0))
    )

    net = s.get('netSavingsUSD', 0)
    ops = (
            t("analytics.operational_summary", context) +
            t("analytics.total_income", context, income=s.get('totalIncomeUSD', 0)) +
            t("analytics.total_expense", context, expense=s.get('totalExpenseUSD', 0)) +
            t("analytics.net_savings", context, net=net, emoji='✅' if net >= 0 else '🔻')
    )

    return header + balance + ops


def _format_habits_message(data):
    if not data:
        return "Could not analyze spending habits."

    day_text = "\n<b>📅 Spending by Day of Week:</b>\n"
    days = sorted(data.get('byDayOfWeek', []), key=lambda x: x.get('total', 0), reverse=True)
    day_text += "\n".join([f"    - {i['day']}s: ${i['total']:,.2f}" for i in days]) or "    - Not enough data.\n"

    kw_text = "\n<b>🏷️ Common Spending Keywords:</b>\n"
    kws = data.get('keywordsByCategory', [])
    if kws:
        for item in kws:
            if item.get('topKeywords'):
                kw_text += f"    - <b>{item['category']}:</b> {', '.join(item['topKeywords'])}\n"
    else:
        kw_text += "    - No descriptions found.\n"

    return day_text + kw_text


def _format_debt_analysis_message(data, context: ContextTypes.DEFAULT_TYPE):
    lent = [d for d in data.get('concentration', []) if d['type'] == 'lent']
    borrowed = [d for d in data.get('concentration', []) if d['type'] == 'borrowed']

    def _fmt_list(items, key_none):
        return "\n".join([
            t('iou.analysis_item', context, person=i['person'], total=i['total'])
            for i in items[:3]
        ]) or t(key_none, context)

    return (
        f"{t('iou.analysis_header', context)}\n"
        f"{t('iou.analysis_lent_header', context)}\n{_fmt_list(lent, 'iou.analysis_lent_none')}\n"
        f"{t('iou.analysis_borrow_header', context)}\n{_fmt_list(borrowed, 'iou.analysis_borrow_none')}"
    )


# --- Charts ---

def _create_income_expense_chart(data, start_date, end_date):
    s = data.get('summary', {})
    inc, exp = s.get('totalIncomeUSD', 0), s.get('totalExpenseUSD', 0)
    if inc == 0 and exp == 0: return None

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.set_title('Operational Income vs. Expense')
    ax.bar(['Income', 'Expense'], [inc, exp], color=['#4CAF50', '#F44336'])
    ax.set_ylabel('Amount (USD)')
    ax.spines[['top', 'right']].set_visible(False)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _create_spending_line_chart(data, start_date, end_date):
    spending = data.get('spendingOverTime', [])
    if not spending: return None

    df = pd.DataFrame(spending)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').reindex(pd.date_range(start_date, end_date), fill_value=0)

    if df['total_spent_usd'].sum() == 0: return None

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df.index, df['total_spent_usd'], marker='o', linestyle='-')
    ax.fill_between(df.index, df['total_spent_usd'], color='skyblue', alpha=0.3)
    ax.set_title('Spending Over Time (USD)')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    fig.autofmt_xdate()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _create_expense_pie_chart(data, start_date, end_date):
    breakdown = data.get('expenseBreakdown', [])
    total = data.get('summary', {}).get('totalExpenseUSD', 0)
    if not breakdown or total == 0: return None

    labels, sizes, other = [], [], 0
    for item in breakdown:
        if (item['totalUSD'] / total) * 100 < 4.0:
            other += item['totalUSD']
        else:
            labels.append(item['category'])
            sizes.append(item['totalUSD'])

    if other > 0:
        labels.append('Other')
        sizes.append(other)

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.set_title('Expense Breakdown')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _create_debt_overview_pie(data):
    usd = data.get('overview_usd', {})
    lent, borrowed = usd.get('total_lent_usd', 0), usd.get('total_borrowed_usd', 0)
    if lent == 0 and borrowed == 0: return None

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.pie([lent, borrowed], labels=['You Are Owed', 'You Owe'], autopct='%1.1f%%', colors=['#4CAF50', '#F44336'])
    ax.set_title('Debt Overview (USD)')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _create_debt_concentration_bar(data):
    conc = data.get('concentration', [])
    if not conc: return None

    lent = sorted([d for d in conc if d['type'] == 'lent'], key=lambda x: x['total'], reverse=True)[:5]
    borrow = sorted([d for d in conc if d['type'] == 'borrowed'], key=lambda x: x['total'], reverse=True)[:5]

    if not lent and not borrow: return None

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

    if lent:
        ax1.barh([d['person'] for d in lent], [d['total'] for d in lent], color='#4CAF50')
        ax1.set_title('You Are Owed (Top 5)')
        ax1.invert_yaxis()

    if borrow:
        ax2.barh([d['person'] for d in borrow], [d['total'] for d in borrow], color='#F44336')
        ax2.set_title('You Owe (Top 5)')
        ax2.invert_yaxis()

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# --- CSV Exports ---

def _create_csv_from_transactions(data):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Type", "Amount", "Currency", "Category", "Description", "ID"])

    for tx in data:
        dt = datetime.fromisoformat(tx['timestamp']).astimezone(PHNOM_PENH_TZ)
        writer.writerow([
            dt.strftime('%Y-%m-%d %H:%M:%S'),
            tx.get('type'), tx.get('amount'), tx.get('currency'),
            tx.get('categoryId'), tx.get('description', ''), tx.get('_id')
        ])

    buf = io.BytesIO()
    buf.write(output.getvalue().encode('utf-8'))
    buf.seek(0)
    return buf


def _create_csv_from_debts(data):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Type", "Person", "Original", "Remaining", "Currency", "Status", "Purpose", "ID"])

    for d in data:
        dt = datetime.fromisoformat(d['created_at']).astimezone(PHNOM_PENH_TZ)
        writer.writerow([
            dt.strftime('%Y-%m-%d'),
            d.get('type'), d.get('person'), d.get('originalAmount'),
            d.get('remainingAmount'), d.get('currency'), d.get('status'),
            d.get('purpose', ''), d.get('_id')
        ])

    buf = io.BytesIO()
    buf.write(output.getvalue().encode('utf-8'))
    buf.seek(0)
    return buf