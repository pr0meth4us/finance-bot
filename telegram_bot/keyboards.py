# --- Start of modified file: telegram_bot/keyboards.py ---
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
        [
            InlineKeyboardButton("📊 Set Balance", callback_data='set_balance_start'),
            InlineKeyboardButton("🔔 Set Reminder", callback_data='set_reminder_start')
        ],
        [
            InlineKeyboardButton("📖 History", callback_data='history'),
            InlineKeyboardButton("🔎 Advanced Search", callback_data='advanced_search')
        ],
        [
            InlineKeyboardButton("📈 Report", callback_data='report_menu'),
            InlineKeyboardButton("🧠 Habits", callback_data='habits_menu')
        ],
        [InlineKeyboardButton("⚙️ Update Rate", callback_data='update_rate')],
        [InlineKeyboardButton("🤝 IOU / Debts", callback_data='iou_menu')],
    ]
    return InlineKeyboardMarkup(keyboard)


def reminder_date_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("Tomorrow", callback_data='remind_date_1'),
            InlineKeyboardButton("In 3 Days", callback_data='remind_date_3'),
            InlineKeyboardButton("In 1 Week", callback_data='remind_date_7')
        ],
        [InlineKeyboardButton("🗓️ Custom Date", callback_data='remind_date_custom')],
        [InlineKeyboardButton("❌ Cancel", callback_data='cancel_conversation')]
    ]
    return InlineKeyboardMarkup(keyboard)


def forgot_day_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("Yesterday", callback_data='forgot_day_1'),
            InlineKeyboardButton("2 Days Ago", callback_data='forgot_day_2')
        ],
        [InlineKeyboardButton("🗓️ Custom Date", callback_data='forgot_day_custom')],
        [InlineKeyboardButton("❌ Cancel", callback_data='cancel_conversation')]
    ]
    return InlineKeyboardMarkup(keyboard)


def iou_date_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("Today", callback_data='iou_date_today'),
            InlineKeyboardButton("Yesterday", callback_data='iou_date_yesterday'),
        ],
        [InlineKeyboardButton("🗓️ Custom Date", callback_data='iou_date_custom')],
        [InlineKeyboardButton("❌ Cancel", callback_data='cancel_conversation')]
    ]
    return InlineKeyboardMarkup(keyboard)


def forgot_type_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💸 Expense", callback_data='forgot_type_expense'),
            InlineKeyboardButton("💰 Income", callback_data='forgot_type_income')
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def report_period_keyboard(is_search=False):
    keyboard = [
        [
            InlineKeyboardButton("🗓️ Today", callback_data='report_period_today'),
            InlineKeyboardButton("🗓️ This Week", callback_data='report_period_this_week'),
        ],
        [
            InlineKeyboardButton("🗓️ This Month", callback_data='report_period_this_month'),
            InlineKeyboardButton("🗓️ Last Week", callback_data='report_period_last_week'),
        ],
        [InlineKeyboardButton("🗓️ Custom Range", callback_data='report_period_custom')],
    ]
    if is_search:
        keyboard.append([InlineKeyboardButton("♾️ All Time", callback_data='report_period_all_time')])

    keyboard.append([InlineKeyboardButton("‹ Back", callback_data='start')])
    return InlineKeyboardMarkup(keyboard)


def search_type_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💸 Expense", callback_data='search_type_expense'),
            InlineKeyboardButton("💰 Income", callback_data='search_type_income')
        ],
        [InlineKeyboardButton("🌐 All Types", callback_data='search_type_all')],
    ]
    return InlineKeyboardMarkup(keyboard)


def skip_keyboard(callback_data):
    keyboard = [
        [InlineKeyboardButton("⏩ Skip", callback_data=callback_data)],
    ]
    return InlineKeyboardMarkup(keyboard)


def search_keyword_logic_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("Must contain ALL (AND)", callback_data='search_logic_and'),
            InlineKeyboardButton("Contains ANY (OR)", callback_data='search_logic_or')
        ]
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
        [InlineKeyboardButton("🔬 Debt Analysis", callback_data='debt_analysis')],
        [InlineKeyboardButton("‹ Back to Main Menu", callback_data='start')],
    ]
    return InlineKeyboardMarkup(keyboard)


def iou_list_keyboard(grouped_debts):
    keyboard = []
    lent = [d for d in grouped_debts if d['type'] == 'lent']
    borrowed = [d for d in grouped_debts if d['type'] == 'borrowed']

    if lent:
        for debt in lent:
            amount_format = ",.0f" if debt['currency'] == 'KHR' else ",.2f"
            label = f"Owed by {debt['person']}: {debt['totalAmount']:{amount_format}} {debt['currency']} ({debt['count']})"
            keyboard.append(
                [InlineKeyboardButton(label, callback_data=f"iou:person:{debt['person']}:{debt['currency']}")])
    if borrowed:
        for debt in borrowed:
            amount_format = ",.0f" if debt['currency'] == 'KHR' else ",.2f"
            label = f"You owe {debt['person']}: {debt['totalAmount']:{amount_format}} {debt['currency']} ({debt['count']})"
            keyboard.append(
                [InlineKeyboardButton(label, callback_data=f"iou:person:{debt['person']}:{debt['currency']}")])

    keyboard.append([InlineKeyboardButton("‹ Back", callback_data='iou_menu')])
    return InlineKeyboardMarkup(keyboard)


def iou_person_detail_keyboard(person_debts, person_name, currency):
    keyboard = [
        [InlineKeyboardButton(f"💰 Record Repayment ({currency})", callback_data=f"iou:repay:{person_name}:{currency}")]
    ]
    for debt in person_debts:
        created_date = datetime.fromisoformat(debt['created_at']).strftime('%d %b')
        purpose = debt.get('purpose') or 'No purpose'
        amount_format = ",.0f" if debt['currency'] == 'KHR' else ",.2f"
        label = f"{debt['remainingAmount']:{amount_format}} {debt['currency']} ({created_date}) - {purpose}"
        callback = f"iou:detail:{debt['_id']}:{person_name}:{currency}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback)])

    keyboard.append([InlineKeyboardButton("‹ Back to Summary", callback_data='iou_view')])
    return InlineKeyboardMarkup(keyboard)


def iou_detail_keyboard(debt_id, person_name, currency):
    keyboard = [
        [InlineKeyboardButton("‹ Back to List", callback_data=f"iou:person:{person_name}:{currency}")],
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
    """ --- THIS FUNCTION HAS BEEN UPDATED --- """
    keyboard = [
        [
            InlineKeyboardButton("🍔 Food", callback_data='cat_Food'),
            InlineKeyboardButton("🍹 Drink", callback_data='cat_Drink')
        ],
        [
            InlineKeyboardButton("🚗 Transport", callback_data='cat_Transport'),
            InlineKeyboardButton("🛍️ Shopping", callback_data='cat_Shopping')
        ],
        [
            InlineKeyboardButton("🧾 Bills", callback_data='cat_Bills'),
            InlineKeyboardButton("💡 Utilities", callback_data='cat_Utilities')
        ],
        [
            InlineKeyboardButton("🎬 Entertainment", callback_data='cat_Entertainment'),
            InlineKeyboardButton("🧴 Personal Care", callback_data='cat_Personal Care')
        ],
        [
            InlineKeyboardButton("💼 Work", callback_data='cat_Work'),
            InlineKeyboardButton("🍺 Alcohol", callback_data='cat_Alcohol')
        ],
        [
            InlineKeyboardButton("🤝 For Others", callback_data='cat_For Others'),
            InlineKeyboardButton("💊 Health", callback_data='cat_Health')
        ],
        [
            InlineKeyboardButton("❓ Forgot", callback_data='cat_Forgot'),
            InlineKeyboardButton("📝 Other", callback_data='cat_other')
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def income_categories_keyboard():
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
        tx_type_emoji = "⬇️" if tx.get('type') == 'expense' else "⬆️"

        amount_format = ",.0f" if currency == 'KHR' else ",.2f"
        label = f"{tx_type_emoji} {amount:{amount_format}} {currency} - {category}"
        callback = f"manage_tx_{tx['_id']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback)])

    keyboard.append([InlineKeyboardButton("‹ Back to Main Menu", callback_data='start')])
    return InlineKeyboardMarkup(keyboard)


def manage_tx_keyboard(tx_id):
    keyboard = [
        [
            InlineKeyboardButton("✏️ Edit", callback_data=f'edit_tx_{tx_id}'),
            InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_tx_{tx_id}')
        ],
        [InlineKeyboardButton("‹ Back to History", callback_data='history')],
    ]
    return InlineKeyboardMarkup(keyboard)


def edit_tx_options_keyboard(tx_id):
    """Keyboard with options for which field to edit."""
    keyboard = [
        [
            InlineKeyboardButton("💰 Amount", callback_data='edit_field_amount_{tx_id}'),
            InlineKeyboardButton("🏷️ Category", callback_data='edit_field_categoryId_{tx_id}'),
        ],
        [
            InlineKeyboardButton("📝 Description", callback_data=f'edit_field_description_{tx_id}'),
        ],
        [InlineKeyboardButton("‹ Cancel Edit", callback_data=f'manage_tx_{tx_id}')],
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