# --- Start of modified file: telegram_bot/keyboards.py ---
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from datetime import datetime

# --- ReplyKeyboardRemove (to hide keyboard) ---
HIDE_KEYBOARD = ReplyKeyboardRemove()

# --- ReplyKeyboards (Static Menus) ---

def main_menu_keyboard():
    keyboard = [
        ["/add_expense", "/add_income"],
        ["/forgot", "/quick_check"],
        ["/balance", "/reminder"],
        ["/history", "/search"],
        ["/report", "/habits"],
        ["/rate", "/get_rate"],
        ["/iou"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def search_menu_keyboard():
    keyboard = [
        ["/search_manage"],
        ["/search_sum"],
        ["/start"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def reminder_date_keyboard():
    keyboard = [
        ["Tomorrow", "In 3 Days", "In 1 Week"],
        ["Custom Date"],
        ["/cancel"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def forgot_day_keyboard():
    keyboard = [
        ["Yesterday", "2 Days Ago"],
        ["Custom Date"],
        ["/cancel"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def iou_date_keyboard():
    keyboard = [
        ["Today", "Yesterday"],
        ["Custom Date"],
        ["/cancel"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def forgot_type_keyboard():
    keyboard = [
        ["💸 Expense", "💰 Income"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def report_period_keyboard(is_search=False):
    keyboard = [
        ["Today", "This Week"],
        ["Last Week", "This Month"],
        ["Last Month", "Custom Range"],
    ]
    if is_search:
        keyboard.append(["♾️ All Time"])
    keyboard.append(["/start"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def search_type_keyboard():
    keyboard = [
        ["💸 Expense", "💰 Income"],
        ["🌐 All Types"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def skip_keyboard():
    keyboard = [
        ["⏩ Skip"],
        ["/cancel"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def search_keyword_logic_keyboard():
    keyboard = [
        ["Must contain ALL (AND)", "Contains ANY (OR)"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def set_balance_account_keyboard():
    keyboard = [
        ["💵 USD Account", "៛ KHR Account"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def iou_menu_keyboard():
    keyboard = [
        ["/iou_lent", "/iou_borrowed"],
        ["/iou_view_open", "/iou_view_settled"],
        ["/iou_analysis"],
        ["/start"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def currency_keyboard():
    keyboard = [
        ["💵 USD", "៛ KHR"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def expense_categories_keyboard():
    keyboard = [
        ["🍔 Food", "🍹 Drink"],
        ["🚗 Transport", "🛍️ Shopping"],
        ["🧾 Bills", "💡 Utilities"],
        ["🎬 Entertainment", "🧴 Personal Care"],
        ["💼 Work", "🍺 Alcohol"],
        ["🤝 For Others", "💊 Health"],
        ["📈 Investment", "❓ Forgot"],
        ["📝 Other"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def income_categories_keyboard():
    keyboard = [
        ["💼 Salary", "📈 Bonus"],
        ["💻 Freelance", "📊 Commission"],
        ["💸 Allowance", "🎁 Gift"],
        ["📈 Investment", "📝 Other"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def ask_remark_keyboard():
    keyboard = [
        ["✅ Add Remark", "⏩ Skip"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


# --- InlineKeyboards (Dynamic Menus) ---
# These must remain as InlineKeyboards because their buttons
# are generated from database data.

def iou_list_keyboard(grouped_debts, is_settled=False):
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

    # This 'Back' button is an inline button, not a command
    keyboard.append([InlineKeyboardButton("‹ Back to IOU Menu", callback_data='iou_menu_inline_placeholder')])
    return InlineKeyboardMarkup(keyboard)


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


def history_keyboard(transactions, is_search_result=False):
    keyboard = []
    # We remove the "Search History" button because "/search" is now on the main keyboard

    for tx in transactions:
        amount = tx.get('amount', 0)
        currency = tx.get('currency', 'N/A')
        category = tx.get('categoryId', 'Unknown')
        tx_type_emoji = "⬇️" if tx.get('type') == 'expense' else "⬆️"

        amount_format = ",.0f" if currency == 'KHR' else ",.2f"
        label = f"{tx_type_emoji} {amount:{amount_format}} {currency} - {category}"
        callback = f"manage_tx_{tx['_id']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback)])

    # This 'Back' button is an inline button
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
    keyboard = [
        [
            InlineKeyboardButton("💰 Amount", callback_data=f'edit_field_amount_{tx_id}'),
            InlineKeyboardButton("🏷️ Category", callback_data=f'edit_field_categoryId_{tx_id}'),
        ],
        [
            InlineKeyboardButton("📝 Description", callback_data=f'edit_field_description_{tx_id}'),
            InlineKeyboardButton("🗓️ Date", callback_data=f'edit_field_timestamp_{tx_id}'),
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