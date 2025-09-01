from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("💸 Add Expense", callback_data='add_expense')],
        [InlineKeyboardButton("💰 Add Income", callback_data='add_income')],
        [InlineKeyboardButton("📖 History", callback_data='history')],
        [InlineKeyboardButton("📈 Monthly Report", callback_data='report')],
        [InlineKeyboardButton("⚙️ Update Rate", callback_data='update_rate')],
        [InlineKeyboardButton("🤝 IOU / Debts", callback_data='iou_menu')],
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

def iou_list_keyboard(debts):
    keyboard = []
    lent = [d for d in debts if d['type'] == 'lent']
    borrowed = [d for d in debts if d['type'] == 'borrowed']

    if lent:
        for debt in lent:
            label = f"Owed by {debt['person']}: {debt['amount']:,} {debt['currency']}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"settle_debt_{debt['_id']}")])
    if borrowed:
        for debt in borrowed:
            label = f"You owe {debt['person']}: {debt['amount']:,} {debt['currency']}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"settle_debt_{debt['_id']}")])

    keyboard.append([InlineKeyboardButton("‹ Back", callback_data='iou_menu')])
    return InlineKeyboardMarkup(keyboard)

def currency_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💵 USD", callback_data='curr_USD'),
            InlineKeyboardButton("៛ KHR", callback_data='curr_KHR')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def categories_keyboard():
    keyboard = [
        [InlineKeyboardButton("🍔 Food", callback_data='cat_Food')],
        [InlineKeyboardButton("🚗 Transport", callback_data='cat_Transport')],
        [InlineKeyboardButton("🛍️ Shopping", callback_data='cat_Shopping')],
        [InlineKeyboardButton("💡 Bills", callback_data='cat_Bills')],
        [InlineKeyboardButton("🎬 Entertainment", callback_data='cat_Entertainment')],
        [InlineKeyboardButton("🏠 Rent", callback_data='cat_Rent')],
        [InlineKeyboardButton("📝 Other", callback_data='cat_other')], # * New "Other" button *
    ]
    return InlineKeyboardMarkup(keyboard)

def ask_remark_keyboard():
    """* New keyboard to ask if the user wants to add a remark. *"""
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
        label = f"{tx['amount']:,} {tx['currency']} - {tx['categoryId']}"
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