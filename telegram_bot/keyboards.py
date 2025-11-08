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
            InlineKeyboardButton("🔎 Search & Analyze", callback_data='search_menu')
        ],
        [
            InlineKeyboardButton("📈 Report", callback_data='report_menu'),
            InlineKeyboardButton("🧠 Habits", callback_data='habits_menu')
        ],
        # --- MODIFIED: Added 'Get Rate' button ---
        [
            InlineKeyboardButton("⚙️ Update Rate", callback_data='update_rate'),
            InlineKeyboardButton("📊 Get Live Rate", callback_data='get_live_rate')
        ],
        [InlineKeyboardButton("🤝 IOU / Debts", callback_data='iou_menu')],
    ]
    return InlineKeyboardMarkup(keyboard)


def search_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("✍️ Find & Manage Transactions", callback_data='start_search_manage')],
        [InlineKeyboardButton("📈 Calculate Totals", callback_data='start_search_sum')],
        [InlineKeyboardButton("‹ Back to Main Menu", callback_data='start')],
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
            InlineKeyboardButton("🗓️ Last Week", callback_data='report_period_last_week'),
            InlineKeyboardButton("🗓️ This Month", callback_data='report_period_this_month'),
        ],
        [
            InlineKeyboardButton("🗓️ Last Month", callback_data='report_period_last_month'),
            InlineKeyboardButton("🗓️ Custom Range", callback_data='report_period_custom'),
        ],
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
        # --- NEW: Add Settled Debts button ---
        [InlineKeyboardButton("✅ View Settled Debts", callback_data='iou_view_settled')],
        [InlineKeyboardButton("🔬 Debt Analysis", callback_data='debt_analysis')],
        [InlineKeyboardButton("‹ Back to Main Menu", callback_data='start')],
    ]
    return InlineKeyboardMarkup(keyboard)


def iou_list_keyboard(grouped_debts, is_settled=False):
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    """Shows a consolidated list of debts grouped by person."""
    keyboard = []
    status_str = "settled" if is_settled else "open"

    lent = [d for d in grouped_debts if d['type'] == 'lent']
    borrowed = [d for d in grouped_debts if d['type'] == 'borrowed']

    def format_totals(totals):
        """Helper to format the totals array, e.g., '60.00 USD (2), 20000 KHR (1)'"""
        parts = []
        for t in totals:
            amount_format = ",.0f" if t['currency'] == 'KHR' else ",.2f"
            parts.append(f"{t['total']:{amount_format}} {t['currency']} ({t['count']})")
        return ", ".join(parts)

    if lent:
        for debt in lent:
            label = f"Owed by {debt['person']}: {format_totals(debt['totals'])}"
            keyboard.append(
                [InlineKeyboardButton(label, callback_data=f"iou:person:{status_str}:{debt['person']}")])
    if borrowed:
        for debt in borrowed:
            label = f"You owe {debt['person']}: {format_totals(debt['totals'])}"
            keyboard.append(
                [InlineKeyboardButton(label, callback_data=f"iou:person:{status_str}:{debt['person']}")])

    keyboard.append([InlineKeyboardButton("‹ Back", callback_data='iou_menu')])
    return InlineKeyboardMarkup(keyboard)


# --- NEW FUNCTION ---
def iou_person_actions_keyboard(person_name, debt_type, is_settled=False):
    """Shows action buttons for the unified person ledger screen."""
    keyboard = []

    if not is_settled:
        # User can only repay/manage open debts
        keyboard.append([
            InlineKeyboardButton("💰 Record Repayment", callback_data=f"iou:repay:{person_name}:{debt_type}"),
            InlineKeyboardButton("✏️ Manage Individual Debts",
                                 callback_data=f"iou:manage:list:{person_name}:{debt_type}:False")
        ])

    back_callback = 'iou_view_settled' if is_settled else 'iou_view'
    keyboard.append([InlineKeyboardButton("‹ Back to Summary", callback_data=back_callback)])
    return InlineKeyboardMarkup(keyboard)


# --- NEW FUNCTION (Renamed from iou_person_detail_keyboard) ---
def iou_manage_list_keyboard(person_debts, person_name, debt_type, is_settled):
    """Displays a list of individual debts for management (Edit/Cancel)."""
    keyboard = []

    for debt in person_debts:
        created_date = datetime.fromisoformat(debt['created_at']).strftime('%d %b')
        purpose = debt.get('purpose') or 'No purpose'
        amount_key = 'remainingAmount' if not is_settled else 'originalAmount'
        amount = debt.get(amount_key, 0)

        amount_format = ",.0f" if debt['currency'] == 'KHR' else ",.2f"
        label = f"{amount:{amount_format}} {debt['currency']} ({created_date}) - {purpose}"

        # Callback leads to the individual debt detail/action screen
        callback = f"iou:detail:{debt['_id']}:{person_name}:{is_settled}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback)])

    # This 'Back' button goes back to the unified ledger view
    back_callback = f"iou:person:settled:{person_name}" if is_settled else f"iou:person:open:{person_name}"
    keyboard.append([InlineKeyboardButton("‹ Back to Ledger", callback_data=back_callback)])
    return InlineKeyboardMarkup(keyboard)


# --- MODIFIED FUNCTION ---
def iou_detail_actions_keyboard(debt_id, person_name, debt_type, is_settled, status):
    """Shows actions for a single, specific debt."""
    keyboard = []

    # Only show edit/cancel buttons if the debt is 'open'
    if status == 'open':
        keyboard.append([
            InlineKeyboardButton("✏️ Edit/Cancel",
                                 callback_data=f"iou:manage:detail:{debt_id}:{person_name}:{is_settled}")
        ])

    # This 'Back' button goes to the "manage list" screen
    back_callback = f"iou:manage:list:{person_name}:{debt_type}:{is_settled}"
    keyboard.append([InlineKeyboardButton("‹ Back to List", callback_data=back_callback)])
    return InlineKeyboardMarkup(keyboard)


# --- NEW FUNCTION ---
def iou_manage_keyboard(debt_id, person, is_settled_str):
    """Keyboard for editing or canceling a debt."""
    keyboard = [
        [
            InlineKeyboardButton("✏️ Edit Person", callback_data=f"iou:edit:person:{debt_id}"),
            InlineKeyboardButton("✏️ Edit Purpose", callback_data=f"iou:edit:purpose:{debt_id}")
        ],
        [
            InlineKeyboardButton("❌ Cancel Debt",
                                 callback_data=f"iou:cancel:prompt:{debt_id}:{person}:{is_settled_str}")
        ],
        [
            # This 'Back' button goes to the specific debt detail screen
            InlineKeyboardButton("‹ Back", callback_data=f"iou:detail:{debt_id}:{person}:{is_settled_str}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- NEW FUNCTION ---
def iou_cancel_confirm_keyboard(debt_id, person, is_settled_str):
    """Confirmation keyboard for canceling a debt."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Cancel Debt", callback_data=f"iou:cancel:confirm:{debt_id}")
        ],
        [
            InlineKeyboardButton("‹ No, Go Back",
                                 callback_data=f"iou:manage:detail:{debt_id}:{person}:{is_settled_str}")
        ]
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
            # --- NEW: Added Investment ---
            InlineKeyboardButton("📈 Investment", callback_data='cat_Investment'),
            InlineKeyboardButton("❓ Forgot", callback_data='cat_Forgot'),
        ],
        [
            InlineKeyboardButton("📝 Other", callback_data='cat_other')
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def income_categories_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💼 Salary", callback_data='cat_Salary'),
            InlineKeyboardButton("📈 Bonus", callback_data='cat_Bonus')
        ],
        [
            InlineKeyboardButton("💻 Freelance", callback_data='cat_Freelance'),
            InlineKeyboardButton("📊 Commission", callback_data='cat_Commission')
        ],
        [
            InlineKeyboardButton("💸 Allowance", callback_data='cat_Allowance'),
            InlineKeyboardButton("🎁 Gift", callback_data='cat_Gift')
        ],
        [
            InlineKeyboardButton("📈 Investment", callback_data='cat_Investment'),
            InlineKeyboardButton("📝 Other", callback_data='cat_other')
        ],
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


def history_keyboard(transactions, is_search_result=False):
    keyboard = []
    if not is_search_result:
        keyboard.append([InlineKeyboardButton("🔎 Search History", callback_data='search_menu')])

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
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    keyboard = [
        [
            InlineKeyboardButton("💰 Amount", callback_data=f'edit_field_amount_{tx_id}'),
            InlineKeyboardButton("🏷️ Category", callback_data=f'edit_field_categoryId_{tx_id}'),
        ],
        [
            InlineKeyboardButton("📝 Description", callback_data=f'edit_field_description_{tx_id}'),
            InlineKeyboardButton("🗓️ Date", callback_data=f'edit_field_timestamp_{tx_id}'),  # <-- FIX: Added Date
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