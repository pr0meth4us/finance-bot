from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime


def main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💸 Add Expense", callback_data='add_expense'),
            InlineKeyboardButton("💰 Add Income", callback_data='add_income')
        ],
        [
            InlineKeyboardButton("🤔 Forgot to Log?", callback_data='forgot_log_start'),
            InlineKeyboardButton("🔍 Quick Check", callback_data='quick_check'),
        ],
        [InlineKeyboardButton("📊 Set Balance", callback_data='set_balance_start')],
        [InlineKeyboardButton("📖 History", callback_data='history')],
        [InlineKeyboardButton("📈 Report", callback_data='report_menu')],
        [InlineKeyboardButton("⚙️ Update Rate", callback_data='update_rate')],
        [InlineKeyboardButton("🤝 IOU / Debts", callback_data='iou_menu')],
    ]
    return InlineKeyboardMarkup(keyboard)


def forgot_day_keyboard():
    """Keyboard to select which past day to log for."""
    keyboard = [
        [
            InlineKeyboardButton("Yesterday", callback_data='forgot_day_1'),
            InlineKeyboardButton("2 Days Ago", callback_data='forgot_day_2')
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data='cancel_conversation')]
    ]
    return InlineKeyboardMarkup(keyboard)


def forgot_type_keyboard():
    """Keyboard to select transaction type for a forgotten log."""
    keyboard = [
        [
            InlineKeyboardButton("💸 Expense", callback_data='forgot_type_expense'),
            InlineKeyboardButton("💰 Income", callback_data='forgot_type_income')
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def report_period_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🗓️ Today", callback_data='report_period_today'),
            InlineKeyboardButton("🗓️ This Week", callback_data='report_period_this_week'),
        ],
        [
            InlineKeyboardButton("🗓️ This Month", callback_data='report_period_this_month'),
            InlineKeyboardButton("🗓️ Last Week", callback_data='report_period_last_week'),
        ],
        [InlineKeyboardButton("‹ Back", callback_data='start')],
    ]
    return InlineKeyboardMarkup(keyboard)


def set_balance_account_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💵 USD Account", callback_data='set_balance_USD'),
            InlineKeyboardButton("៛ KHR Account", callback_data='set_balance_KHR')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def iou_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("➡️ I Lent Money", callback_data='iou_lent')],
        [InlineKeyboardButton("⬅️ I Borrowed Money", callback_data='iou_borrowed')],
        [InlineKeyboardButton("📖 View Open Debts", callback_data='iou_view')],
        [InlineKeyboardButton("‹ Back to Main Menu", callback_data='start')],
    ]
    return InlineKeyboardMarkup(keyboard)


def iou_list_keyboard(grouped_debts):
    """Creates a keyboard for debts grouped by person."""
    keyboard = []
    lent = [d for d in grouped_debts if d['type'] == 'lent']
    borrowed = [d for d in grouped_debts if d['type'] == 'borrowed']

    if lent:
        for debt in lent:
            label = f"Owed by {debt['person']}: {debt['totalAmount']:,.2f} {debt['currency']} ({debt['count']})"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"iou_person_{debt['person']}")])
    if borrowed:
        for debt in borrowed:
            label = f"You owe {debt['person']}: {debt['totalAmount']:,.2f} {debt['currency']} ({debt['count']})"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"iou_person_{debt['person']}")])

    keyboard.append([InlineKeyboardButton("‹ Back", callback_data='iou_menu')])
    return InlineKeyboardMarkup(keyboard)


def iou_person_detail_keyboard(person_debts):
    """Creates a keyboard for an individual person's debts, including the date."""
    keyboard = []
    person_name = person_debts[0]['person'] if person_debts else ''

    for debt in person_debts:
        created_date = datetime.fromisoformat(debt['created_at']).strftime('%d %b')
        purpose = debt.get('purpose') or 'No purpose'
        label = f"{debt['remainingAmount']:,.2f} {debt['currency']} ({created_date}) - {purpose}"
        callback = f"iou_detail_{debt['_id']}_{person_name}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback)])

    keyboard.append([InlineKeyboardButton("‹ Back to Summary", callback_data='iou_view')])
    return InlineKeyboardMarkup(keyboard)


def iou_detail_keyboard(debt_id, person_name):
    """Creates keyboard for a single debt, with a back button to the person's list."""
    keyboard = [
        [InlineKeyboardButton("💵 Record Repayment", callback_data=f"repay_start_{debt_id}")],
        [InlineKeyboardButton("‹ Back to List", callback_data=f"iou_person_{person_name}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def currency_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💵 USD", callback_data='curr_USD'),
            InlineKeyboardButton("៛ KHR", callback_data='curr_KHR')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def expense_categories_keyboard():
    """* Categories specifically for expenses. *"""
    keyboard = [
        [InlineKeyboardButton("🍔 Food", callback_data='cat_Food')],
        [
            InlineKeyboardButton("🍹 Drink", callback_data='cat_Drink'),
            InlineKeyboardButton("🍺 Alcohol", callback_data='cat_Alcohol')
        ],
        [InlineKeyboardButton("🚗 Transport", callback_data='cat_Transport')],
        [InlineKeyboardButton("🛍️ Shopping", callback_data='cat_Shopping')],
        [InlineKeyboardButton("💡 Bills", callback_data='cat_Bills')],
        [InlineKeyboardButton("🎬 Entertainment", callback_data='cat_Entertainment')],
        [InlineKeyboardButton("🏠 Rent", callback_data='cat_Rent')],
        [InlineKeyboardButton("📝 Other", callback_data='cat_other')],
    ]
    return InlineKeyboardMarkup(keyboard)


def income_categories_keyboard():
    """* New keyboard specifically for income sources. *"""
    keyboard = [
        [InlineKeyboardButton("💼 Salary", callback_data='cat_Salary')],
        [InlineKeyboardButton("📈 Bonus", callback_data='cat_Bonus')],
        [InlineKeyboardButton("🎁 Gift", callback_data='cat_Gift')],
        [InlineKeyboardButton("📈 Investment", callback_data='cat_Investment')],
        [InlineKeyboardButton("📝 Other", callback_data='cat_other')],
    ]
    return InlineKeyboardMarkup(keyboard)


def ask_remark_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("✅ Add Remark", callback_data='remark_yes'),
            InlineKeyboardButton("⏩ Skip", callback_data='remark_no')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def history_keyboard(transactions):
    keyboard = []
    for tx in transactions:
        amount = tx.get('amount', 0)
        currency = tx.get('currency', 'N/A')
        category = tx.get('categoryId', 'Unknown')

        label = f"{amount:,.2f} {currency} - {category}"
        callback = f"manage_tx_{tx['_id']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback)])

    keyboard.append([InlineKeyboardButton("‹ Back to Main Menu", callback_data='start')])
    return InlineKeyboardMarkup(keyboard)


def manage_tx_keyboard(tx_id):
    keyboard = [
        [InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_tx_{tx_id}')],
        [InlineKeyboardButton("‹ Back to History", callback_data='history')],
    ]
    return InlineKeyboardMarkup(keyboard)


def confirm_delete_keyboard(tx_id):
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f'confirm_delete_{tx_id}'),
            InlineKeyboardButton("❌ No, Cancel", callback_data=f'manage_tx_{tx_id}')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)