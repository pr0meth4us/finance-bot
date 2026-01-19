# telegram_bot/keyboards.py

from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.i18n import t


def _get_mode_and_currencies(context: ContextTypes.DEFAULT_TYPE):
    """Helper to extract mode and currencies from cached profile."""
    profile = context.user_data.get('profile', {})
    settings = profile.get('settings', {})
    mode = settings.get('currency_mode', 'dual')

    if mode == 'single':
        primary = settings.get('primary_currency', 'USD')
        return mode, (primary,)

    return 'dual', ('USD', 'KHR')


# --- Main Menu ---

def main_menu_keyboard(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.add_expense", context), callback_data='add_expense'),
            InlineKeyboardButton(t("keyboards.add_income", context), callback_data='add_income')
        ],
        [
            InlineKeyboardButton(t("keyboards.forgot_log", context), callback_data='forgot_log_start'),
            InlineKeyboardButton(t("keyboards.quick_check", context), callback_data='quick_check'),
        ],
        [
            InlineKeyboardButton(t("keyboards.set_reminder", context), callback_data='set_reminder_start'),
            InlineKeyboardButton(t("keyboards.iou_menu", context), callback_data='iou_menu')
        ],
        [
            InlineKeyboardButton(t("keyboards.history", context), callback_data='history'),
            InlineKeyboardButton(t("keyboards.search", context), callback_data='search_menu')
        ],
        [
            InlineKeyboardButton(t("keyboards.report", context), callback_data='report_menu'),
            InlineKeyboardButton(t("keyboards.habits", context), callback_data='habits_menu')
        ],
        [
            InlineKeyboardButton(t("keyboards.get_live_rate", context), callback_data='get_live_rate'),
            InlineKeyboardButton(t("keyboards.settings", context), callback_data='settings_menu')
        ],
        [
            InlineKeyboardButton(t("keyboards.web_dashboard", context), url="https://savvify-web.vercel.app/")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- Transaction & History ---

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

    # FIXED: Callback data 'menu'
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


# --- IOU / Debts ---

def iou_menu_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("keyboards.iou_lent", context), callback_data='iou_lent')],
        [InlineKeyboardButton(t("keyboards.iou_borrowed", context), callback_data='iou_borrowed')],
        [InlineKeyboardButton(t("keyboards.iou_view_open", context), callback_data='iou_view')],
        [InlineKeyboardButton(t("keyboards.iou_view_settled", context), callback_data='iou_view_settled')],
        [InlineKeyboardButton(t("keyboards.iou_analysis", context), callback_data='debt_analysis')],
        # FIXED: Callback data 'menu'
        [InlineKeyboardButton(t("keyboards.back_to_main", context), callback_data='menu')],
    ])


def iou_list_keyboard(grouped_debts, context: ContextTypes.DEFAULT_TYPE, is_settled=False):
    keyboard = []
    status_str = "settled" if is_settled else "open"
    _, currencies = _get_mode_and_currencies(context)

    def format_totals(totals):
        parts = []
        for t in totals:
            if t['currency'] in currencies:
                fmt = ",.0f" if t['currency'] == 'KHR' else ",.2f"
                parts.append(f"{t['total']:{fmt}} {t['currency']} ({t['count']})")
        return ", ".join(parts) if parts else None

    # Separate by type for cleaner list
    for d in grouped_debts:
        total_str = format_totals(d['totals'])
        if not total_str: continue

        key = "keyboards.iou_person_lent" if d['type'] == 'lent' else "keyboards.iou_person_borrowed"
        label = t(key, context, person=d['person'], totals=total_str)

        keyboard.append([
            InlineKeyboardButton(label, callback_data=f"iou:person:{status_str}:{d['person']}")
        ])

    keyboard.append([InlineKeyboardButton(t("keyboards.back", context), callback_data='iou_menu')])
    return InlineKeyboardMarkup(keyboard)


def iou_person_actions_keyboard(person_name, debt_type, context: ContextTypes.DEFAULT_TYPE, is_settled=False):
    keyboard = []
    if not is_settled:
        keyboard.append([
            InlineKeyboardButton(t("keyboards.iou_record_repayment", context),
                                 callback_data=f"iou:repay:{person_name}:{debt_type}"),
            InlineKeyboardButton(t("keyboards.iou_manage_individual", context),
                                 callback_data=f"iou:manage:list:{person_name}:{debt_type}:False")
        ])

    back_cb = 'iou_view_settled' if is_settled else 'iou_view'
    keyboard.append([InlineKeyboardButton(t("keyboards.back_to_summary", context), callback_data=back_cb)])
    return InlineKeyboardMarkup(keyboard)


def iou_manage_list_keyboard(person_debts, person_name, debt_type, is_settled, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    _, currencies = _get_mode_and_currencies(context)

    for debt in person_debts:
        if debt.get('currency') not in currencies: continue

        created_date = datetime.fromisoformat(debt['created_at']).strftime('%d %b')
        amount = debt.get('originalAmount' if is_settled else 'remainingAmount', 0)
        curr = debt.get('currency')
        fmt = ",.0f" if curr == 'KHR' else ",.2f"

        label = f"{amount:{fmt}} {curr} ({created_date}) - {debt.get('purpose') or 'No purpose'}"
        keyboard.append(
            [InlineKeyboardButton(label, callback_data=f"iou:detail:{debt['_id']}:{person_name}:{is_settled}")])

    back_cb = f"iou:person:{'settled' if is_settled else 'open'}:{person_name}"
    keyboard.append([InlineKeyboardButton(t("keyboards.back_to_ledger", context), callback_data=back_cb)])
    return InlineKeyboardMarkup(keyboard)


def iou_detail_actions_keyboard(debt_id, person_name, debt_type, is_settled, status,
                                context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    if status == 'open':
        keyboard.append([
            InlineKeyboardButton(
                t("keyboards.iou_edit_cancel", context),
                callback_data=f"iou:manage:detail:{debt_id}:{person_name}:{is_settled}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            t("keyboards.back_to_list", context),
            callback_data=f"iou:manage:list:{person_name}:{debt_type}:{is_settled}"
        )
    ])
    return InlineKeyboardMarkup(keyboard)


def iou_manage_keyboard(debt_id, person, is_settled_str, context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("keyboards.iou_edit_person", context), callback_data=f"iou:edit:person:{debt_id}"),
            InlineKeyboardButton(t("keyboards.iou_edit_purpose", context), callback_data=f"iou:edit:purpose:{debt_id}")
        ],
        [
            InlineKeyboardButton(t("keyboards.iou_cancel_debt", context),
                                 callback_data=f"iou:cancel:prompt:{debt_id}:{person}:{is_settled_str}")
        ],
        [
            InlineKeyboardButton(t("keyboards.back", context),
                                 callback_data=f"iou:detail:{debt_id}:{person}:{is_settled_str}")
        ]
    ])


def iou_cancel_confirm_keyboard(debt_id, person, is_settled_str, context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("keyboards.iou_cancel_confirm", context),
                              callback_data=f"iou:cancel:confirm:{debt_id}")],
        [InlineKeyboardButton(t("keyboards.iou_cancel_go_back", context),
                              callback_data=f"iou:manage:detail:{debt_id}:{person}:{is_settled_str}")]
    ])


def debt_analysis_actions_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("keyboards.download_open_debts_csv", context), callback_data="debt_analysis_csv")],
        [InlineKeyboardButton(t("keyboards.back_to_iou", context), callback_data='iou_menu')],
    ])


def iou_date_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("keyboards.today", context), callback_data='iou_date_today'),
            InlineKeyboardButton(t("keyboards.yesterday", context), callback_data='iou_date_yesterday'),
        ],
        [InlineKeyboardButton(t("keyboards.custom_date", context), callback_data='iou_date_custom')],
        [InlineKeyboardButton(t("keyboards.cancel", context), callback_data='cancel_conversation')]
    ])


# --- Analytics & Search ---

def report_period_keyboard(context: ContextTypes.DEFAULT_TYPE, is_search=False):
    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.period_today", context), callback_data='report_period_today'),
            InlineKeyboardButton(t("keyboards.period_this_week", context), callback_data='report_period_this_week'),
        ],
        [
            InlineKeyboardButton(t("keyboards.period_last_week", context), callback_data='report_period_last_week'),
            InlineKeyboardButton(t("keyboards.period_this_month", context), callback_data='report_period_this_month'),
        ],
        [
            InlineKeyboardButton(t("keyboards.period_last_month", context), callback_data='report_period_last_month'),
            InlineKeyboardButton(t("keyboards.period_custom", context), callback_data='report_period_custom'),
        ],
    ]
    if is_search:
        keyboard.append(
            [InlineKeyboardButton(t("keyboards.period_all_time", context), callback_data='report_period_all_time')])

    # FIXED: Callback data 'menu'
    keyboard.append([InlineKeyboardButton(t("keyboards.back", context), callback_data='menu')])
    return InlineKeyboardMarkup(keyboard)


def search_menu_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("keyboards.search_manage", context), callback_data='start_search_manage')],
        [InlineKeyboardButton(t("keyboards.search_sum", context), callback_data='start_search_sum')],
        # FIXED: Callback data 'menu'
        [InlineKeyboardButton(t("keyboards.back_to_main", context), callback_data='menu')],
    ])


def search_type_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("keyboards.expense", context), callback_data='search_type_expense'),
            InlineKeyboardButton(t("keyboards.income", context), callback_data='search_type_income')
        ],
        [InlineKeyboardButton(t("keyboards.all_types", context), callback_data='search_type_all')],
    ])


def search_keyword_logic_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("keyboards.search_logic_and", context), callback_data='search_logic_and'),
            InlineKeyboardButton(t("keyboards.search_logic_or", context), callback_data='search_logic_or')
        ]
    ])


def report_actions_keyboard(start_date, end_date, context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("keyboards.download_report_csv", context),
                              callback_data=f"report_csv:{start_date}:{end_date}")],
        # FIXED: Callback data 'menu'
        [InlineKeyboardButton(t("keyboards.back_to_main", context), callback_data='menu')],
    ])


# --- Settings ---

def settings_menu_keyboard(context: ContextTypes.DEFAULT_TYPE):
    mode, _ = _get_mode_and_currencies(context)

    keyboard = [
        [InlineKeyboardButton(t("keyboards.settings_update_balances", context), callback_data='settings_set_balance')],
        [InlineKeyboardButton(t("keyboards.settings_manage_categories", context),
                              callback_data='settings_manage_categories')],
        [InlineKeyboardButton(t("keyboards.settings_change_language", context),
                              callback_data='settings_change_language')],
        # NEW: Link Email for Web Login
        [InlineKeyboardButton(t("keyboards.settings_link_email", context), callback_data='settings_link_email')],
    ]

    if mode == 'dual':
        keyboard.append(
            [InlineKeyboardButton(t("keyboards.settings_update_rate", context), callback_data='settings_set_rate')])
    elif mode == 'single':
        keyboard.append([InlineKeyboardButton(t("keyboards.settings_switch_to_dual", context),
                                              callback_data='settings_switch_to_dual')])

    # FIXED: Callback data 'menu'
    keyboard.append([InlineKeyboardButton(t("keyboards.back_to_main", context), callback_data='menu')])
    return InlineKeyboardMarkup(keyboard)


def set_balance_account_keyboard(context: ContextTypes.DEFAULT_TYPE, mode: str, currencies: tuple):
    keyboard = []
    if mode == 'dual':
        keyboard.append([
            InlineKeyboardButton(t("keyboards.usd_account", context), callback_data='set_balance_USD'),
            InlineKeyboardButton(t("keyboards.khr_account", context), callback_data='set_balance_KHR')
        ])
    else:
        curr = currencies[0]
        keyboard.append([
            InlineKeyboardButton(t("keyboards.update_balance", context, currency=curr),
                                 callback_data=f'set_balance_{curr}'),
        ])

    keyboard.append([InlineKeyboardButton(t("keyboards.back_to_settings", context), callback_data='settings_menu')])
    return InlineKeyboardMarkup(keyboard)


def manage_categories_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("keyboards.category_add", context), callback_data='category_add'),
            InlineKeyboardButton(t("keyboards.category_remove", context), callback_data='category_remove')
        ],
        [InlineKeyboardButton(t("keyboards.back_to_settings", context), callback_data='settings_menu')]
    ])


def category_type_keyboard(context: ContextTypes.DEFAULT_TYPE, action: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("keyboards.expense", context), callback_data=f'cat_type:{action}:expense'),
            InlineKeyboardButton(t("keyboards.income", context), callback_data=f'cat_type:{action}:income')
        ],
        [InlineKeyboardButton(t("keyboards.back", context), callback_data='settings_manage_categories')]
    ])


def change_language_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("English", callback_data='change_lang:en'),
            InlineKeyboardButton("ភាសាខ្មែរ", callback_data='change_lang:km')
        ],
        [InlineKeyboardButton(t("keyboards.back_to_settings", context), callback_data="settings_menu")]
    ])


def switch_to_dual_confirm_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("keyboards.switch_dual_confirm", context), callback_data='confirm_switch_dual')],
        [InlineKeyboardButton(t("keyboards.switch_dual_cancel", context), callback_data="settings_menu")]
    ])


# --- Subscription / Onboarding ---

def subscription_tier_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("keyboards.plan_free", context), callback_data='plan_free')],
        [InlineKeyboardButton(t("keyboards.plan_premium", context), callback_data='plan_premium')],
    ])


# --- Utilities ---

def reminder_date_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("keyboards.tomorrow", context), callback_data='remind_date_1'),
            InlineKeyboardButton(t("keyboards.in_3_days", context), callback_data='remind_date_3'),
            InlineKeyboardButton(t("keyboards.in_1_week", context), callback_data='remind_date_7')
        ],
        [InlineKeyboardButton(t("keyboards.custom_date", context), callback_data='remind_date_custom')],
        [InlineKeyboardButton(t("keyboards.cancel", context), callback_data='cancel_conversation')]
    ])


def skip_keyboard(context: ContextTypes.DEFAULT_TYPE, callback_data):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("keyboards.skip", context), callback_data=callback_data)],
    ])