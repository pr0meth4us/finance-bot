# telegram_bot/keyboards/transactions.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.i18n import t
from .utils import _get_mode_and_currencies

def expense_categories_keyboard(categories: list, context: ContextTypes.DEFAULT_TYPE):
    """Builds a dynamic keyboard for expense categories."""
    return _build_category_keyboard(categories, context, 'cat_')


def income_categories_keyboard(categories: list, context: ContextTypes.DEFAULT_TYPE):
    """Builds a dynamic keyboard for income categories."""
    return _build_category_keyboard(categories, context, 'cat_')


def _build_category_keyboard(categories: list, context: ContextTypes.DEFAULT_TYPE, prefix: str):
    keyboard = []
    row = []
    for category in categories:
        text = t(f"categories.{category}", context)
        row.append(InlineKeyboardButton(text, callback_data=f'{prefix}{category}'))
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(t("keyboards.other", context), callback_data=f'{prefix}other')])
    return InlineKeyboardMarkup(keyboard)


def currency_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💵 USD", callback_data='curr_USD'),
            InlineKeyboardButton("៛ KHR", callback_data='curr_KHR')
        ]
    ])


def ask_remark_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("keyboards.add_remark", context), callback_data='remark_yes'),
            InlineKeyboardButton(t("keyboards.skip", context), callback_data='remark_no')
        ]
    ])


def history_keyboard(transactions, context: ContextTypes.DEFAULT_TYPE, is_search_result=False):
    keyboard = []
    if not is_search_result:
        keyboard.append([InlineKeyboardButton(t("keyboards.search", context), callback_data='search_menu')])

    _, currencies = _get_mode_and_currencies(context)

    for tx in transactions:
        if tx.get('currency') not in currencies:
            continue

        amount = tx.get('amount', 0)
        curr = tx.get('currency', 'N/A')
        cat = tx.get('categoryId', 'Unknown')
        emoji = "⬇️" if tx.get('type') == 'expense' else "⬆️"
        fmt = ",.0f" if curr == 'KHR' else ",.2f"

        label = f"{emoji} {amount:{fmt}} {curr} - {cat}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"manage_tx_{tx['_id']}")])

    keyboard.append([InlineKeyboardButton(t("keyboards.back_to_main", context), callback_data='menu')])
    return InlineKeyboardMarkup(keyboard)


def manage_tx_keyboard(tx_id, context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("keyboards.edit", context), callback_data=f'edit_tx_{tx_id}'),
            InlineKeyboardButton(t("keyboards.delete", context), callback_data=f'delete_tx_{tx_id}')
        ],
        [InlineKeyboardButton(t("keyboards.back_to_history", context), callback_data='history')]
    ])


def edit_tx_options_keyboard(tx_id, context: ContextTypes.DEFAULT_TYPE):
    mode, _ = _get_mode_and_currencies(context)

    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.edit_amount", context), callback_data=f'edit_field_amount_{tx_id}'),
            InlineKeyboardButton(t("keyboards.edit_category", context), callback_data=f'edit_field_categoryId_{tx_id}'),
        ],
        [
            InlineKeyboardButton(t("keyboards.edit_description", context),
                                 callback_data=f'edit_field_description_{tx_id}'),
            InlineKeyboardButton(t("keyboards.edit_date", context), callback_data=f'edit_field_timestamp_{tx_id}'),
        ],
    ]

    if mode == 'dual':
        keyboard.append([
            InlineKeyboardButton(t("keyboards.edit_currency", context), callback_data=f'edit_field_currency_{tx_id}')
        ])

    keyboard.append([InlineKeyboardButton(t("keyboards.edit_cancel", context), callback_data=f'manage_tx_{tx_id}')])
    return InlineKeyboardMarkup(keyboard)


def confirm_delete_keyboard(tx_id, context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("keyboards.delete_confirm", context), callback_data=f'confirm_delete_{tx_id}'),
            InlineKeyboardButton(t("keyboards.delete_cancel", context), callback_data=f'manage_tx_{tx_id}')
        ]
    ])


def forgot_day_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("keyboards.yesterday", context), callback_data='forgot_day_1'),
            InlineKeyboardButton(t("keyboards.days_ago", context, days=2), callback_data='forgot_day_2')
        ],
        [InlineKeyboardButton(t("keyboards.custom_date", context), callback_data='forgot_day_custom')],
        [InlineKeyboardButton(t("keyboards.cancel", context), callback_data='cancel_conversation')]
    ])


def forgot_type_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("keyboards.expense", context), callback_data='forgot_type_expense'),
            InlineKeyboardButton(t("keyboards.income", context), callback_data='forgot_type_income')
        ],
    ])