# --- Start of modified file: telegram_bot/keyboards.py ---
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
from telegram.ext import ContextTypes
from utils.i18n import t


def _get_user_settings_for_keyboards(context: ContextTypes.DEFAULT_TYPE):
    """Helper to safely get user settings and currency mode."""
    profile = context.user_data.get('user_profile', {})
    settings = profile.get('settings', {})
    mode = settings.get('currency_mode', 'dual')

    if mode == 'single':
        primary_currency = settings.get('primary_currency', 'USD')
        return mode, (primary_currency,)

    return 'dual', ('USD', 'KHR')


def main_menu_keyboard(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(
                t("keyboards.add_expense", context),
                callback_data='add_expense'
            ),
            InlineKeyboardButton(
                t("keyboards.add_income", context),
                callback_data='add_income'
            )
        ],
        [
            InlineKeyboardButton(
                t("keyboards.forgot_log", context),
                callback_data='forgot_log_start'
            ),
            InlineKeyboardButton(
                t("keyboards.quick_check", context),
                callback_data='quick_check'
            ),
        ],
        [
            InlineKeyboardButton(
                t("keyboards.set_reminder", context),
                callback_data='set_reminder_start'
            ),
            InlineKeyboardButton(
                t("keyboards.iou_menu", context),
                callback_data='iou_menu'
            )
        ],
        [
            InlineKeyboardButton(
                t("keyboards.history", context),
                callback_data='history'
            ),
            InlineKeyboardButton(
                t("keyboards.search", context),
                callback_data='search_menu'
            )
        ],
        [
            InlineKeyboardButton(
                t("keyboards.report", context),
                callback_data='report_menu'
            ),
            InlineKeyboardButton(
                t("keyboards.habits", context),
                callback_data='habits_menu'
            )
        ],
        [
            InlineKeyboardButton(
                t("keyboards.get_live_rate", context),
                callback_data='get_live_rate'
            ),
            InlineKeyboardButton(
                t("keyboards.settings", context),
                callback_data='settings_menu'
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def report_actions_keyboard(start_date, end_date,
                            context: ContextTypes.DEFAULT_TYPE):
    """Keyboard shown after a report is generated."""
    callback_data = f"report_csv:{start_date.isoformat()}:{end_date.isoformat()}"
    keyboard = [
        [
            InlineKeyboardButton(
                t("keyboards.download_report_csv", context), # <-- MODIFIED
                callback_data=callback_data
            )
        ],
        [InlineKeyboardButton(t("keyboards.back_to_main", context), callback_data='start')], # <-- MODIFIED
    ]
    return InlineKeyboardMarkup(keyboard)


def debt_analysis_actions_keyboard(context: ContextTypes.DEFAULT_TYPE):
    """Keyboard shown after debt analysis is generated."""
    keyboard = [
        [
            InlineKeyboardButton(
                t("keyboards.download_open_debts_csv", context), # <-- MODIFIED
                callback_data="debt_analysis_csv"
            )
        ],
        [InlineKeyboardButton(t("keyboards.back_to_iou", context), callback_data='iou_menu')], # <-- MODIFIED
    ]
    return InlineKeyboardMarkup(keyboard)


def search_menu_keyboard(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(
            t("keyboards.search_manage", context), # <-- MODIFIED
            callback_data='start_search_manage'
        )],
        [InlineKeyboardButton(
            t("keyboards.search_sum", context), # <-- MODIFIED
            callback_data='start_search_sum'
        )],
        [InlineKeyboardButton(t("keyboards.back_to_main", context), callback_data='start')], # <-- MODIFIED
    ]
    return InlineKeyboardMarkup(keyboard)


def reminder_date_keyboard(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.tomorrow", context), callback_data='remind_date_1'), # <-- MODIFIED
            InlineKeyboardButton(t("keyboards.in_3_days", context), callback_data='remind_date_3'), # <-- MODIFIED
            InlineKeyboardButton(t("keyboards.in_1_week", context), callback_data='remind_date_7') # <-- MODIFIED
        ],
        [InlineKeyboardButton(t("keyboards.custom_date", context), # <-- MODIFIED
                              callback_data='remind_date_custom')],
        [InlineKeyboardButton(t("keyboards.cancel", context), # <-- MODIFIED
                              callback_data='cancel_conversation')]
    ]
    return InlineKeyboardMarkup(keyboard)


def forgot_day_keyboard(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.yesterday", context), callback_data='forgot_day_1'), # <-- MODIFIED
            InlineKeyboardButton(t("keyboards.days_ago", context, days=2), callback_data='forgot_day_2') # <-- MODIFIED
        ],
        [InlineKeyboardButton(t("keyboards.custom_date", context), # <-- MODIFIED
                              callback_data='forgot_day_custom')],
        [InlineKeyboardButton(t("keyboards.cancel", context), # <-- MODIFIED
                              callback_data='cancel_conversation')]
    ]
    return InlineKeyboardMarkup(keyboard)


def iou_date_keyboard(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.today", context), callback_data='iou_date_today'), # <-- MODIFIED
            InlineKeyboardButton(t("keyboards.yesterday", context), # <-- MODIFIED
                                 callback_data='iou_date_yesterday'),
        ],
        [InlineKeyboardButton(t("keyboards.custom_date", context), # <-- MODIFIED
                              callback_data='iou_date_custom')],
        [InlineKeyboardButton(t("keyboards.cancel", context), # <-- MODIFIED
                              callback_data='cancel_conversation')]
    ]
    return InlineKeyboardMarkup(keyboard)


def forgot_type_keyboard(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.expense", context), # <-- MODIFIED
                                 callback_data='forgot_type_expense'),
            InlineKeyboardButton(t("keyboards.income", context), # <-- MODIFIED
                                 callback_data='forgot_type_income')
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def report_period_keyboard(context: ContextTypes.DEFAULT_TYPE, is_search=False):
    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.period_today", context), # <-- MODIFIED
                                 callback_data='report_period_today'),
            InlineKeyboardButton(t("keyboards.period_this_week", context), # <-- MODIFIED
                                 callback_data='report_period_this_week'),
        ],
        [
            InlineKeyboardButton(t("keyboards.period_last_week", context), # <-- MODIFIED
                                 callback_data='report_period_last_week'),
            InlineKeyboardButton(t("keyboards.period_this_month", context), # <-- MODIFIED
                                 callback_data='report_period_this_month'),
        ],
        [
            InlineKeyboardButton(t("keyboards.period_last_month", context), # <-- MODIFIED
                                 callback_data='report_period_last_month'),
            InlineKeyboardButton(t("keyboards.period_custom", context), # <-- MODIFIED
                                 callback_data='report_period_custom'),
        ],
    ]
    if is_search:
        keyboard.append([InlineKeyboardButton(
            t("keyboards.period_all_time", context), # <-- MODIFIED
            callback_data='report_period_all_time'
        )])

    keyboard.append([InlineKeyboardButton(t("keyboards.back", context), callback_data='start')]) # <-- MODIFIED
    return InlineKeyboardMarkup(keyboard)


def search_type_keyboard(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.expense", context), # <-- MODIFIED
                                 callback_data='search_type_expense'),
            InlineKeyboardButton(t("keyboards.income", context), # <-- MODIFIED
                                 callback_data='search_type_income')
        ],
        [InlineKeyboardButton(t("keyboards.all_types", context), callback_data='search_type_all')], # <-- MODIFIED
    ]
    return InlineKeyboardMarkup(keyboard)


def skip_keyboard(context: ContextTypes.DEFAULT_TYPE, callback_data):
    keyboard = [
        [InlineKeyboardButton(t("keyboards.skip", context), callback_data=callback_data)], # <-- MODIFIED
    ]
    return InlineKeyboardMarkup(keyboard)


def search_keyword_logic_keyboard(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.search_logic_and", context), # <-- MODIFIED
                                 callback_data='search_logic_and'),
            InlineKeyboardButton(t("keyboards.search_logic_or", context), # <-- MODIFIED
                                 callback_data='search_logic_or')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def settings_menu_keyboard(context: ContextTypes.DEFAULT_TYPE):
    mode, currencies = _get_user_settings_for_keyboards(context)

    keyboard = [
        [
            InlineKeyboardButton(
                t("keyboards.settings_update_balances", context), # <-- MODIFIED
                callback_data='settings_set_balance'
            )
        ],
        [
            InlineKeyboardButton(
                t("keyboards.settings_manage_categories", context), # <-- MODIFIED
                callback_data='settings_manage_categories'
            )
        ],
    ]

    # Only show rate and mode-switch options to dual-currency users
    # or single-currency users (to let them switch *to* dual)
    if mode == 'dual':
        keyboard.append([
            InlineKeyboardButton(
                t("keyboards.settings_update_rate", context), callback_data='settings_set_rate' # <-- MODIFIED
            )
        ])
    elif mode == 'single':
        keyboard.append([
            InlineKeyboardButton(
                t("keyboards.settings_switch_to_dual", context), # <-- MODIFIED
                callback_data='settings_switch_to_dual'
            )
        ])

    keyboard.append([InlineKeyboardButton(t("keyboards.back_to_main", context), callback_data='start')]) # <-- MODIFIED
    return InlineKeyboardMarkup(keyboard)


def set_balance_account_keyboard(context: ContextTypes.DEFAULT_TYPE, mode: str, currencies: tuple):
    keyboard = []

    if mode == 'dual':
        keyboard.append([
            InlineKeyboardButton(t("keyboards.usd_account", context), # <-- MODIFIED
                                 callback_data='set_balance_USD'),
            InlineKeyboardButton(t("keyboards.khr_account", context), # <-- MODIFIED
                                 callback_data='set_balance_KHR')
        ])
    else:
        # Single currency mode
        curr = currencies[0]
        keyboard.append([
            InlineKeyboardButton(t("keyboards.update_balance", context, currency=curr), # <-- MODIFIED
                                 callback_data=f'set_balance_{curr}'),
        ])

    keyboard.append([InlineKeyboardButton(t("keyboards.back_to_settings", context), # <-- MODIFIED
                                          callback_data='settings_menu')])
    return InlineKeyboardMarkup(keyboard)


def switch_to_dual_confirm_keyboard(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(
                t("keyboards.switch_dual_confirm", context), # <-- MODIFIED
                callback_data='confirm_switch_dual'
            )
        ],
        [
            InlineKeyboardButton(
                t("keyboards.switch_dual_cancel", context), # <-- MODIFIED
                callback_data="settings_menu"
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def manage_categories_keyboard(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.category_add", context), # <-- MODIFIED
                                 callback_data='category_add'),
            InlineKeyboardButton(t("keyboards.category_remove", context), # <-- MODIFIED
                                 callback_data='category_remove')
        ],
        [InlineKeyboardButton(t("keyboards.back_to_settings", context), # <-- MODIFIED
                              callback_data='settings_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)


def category_type_keyboard(context: ContextTypes.DEFAULT_TYPE, action: str):
    """Generates a keyboard to select category type (expense/income)."""
    keyboard = [
        [
            InlineKeyboardButton(
                t("keyboards.expense", context), callback_data=f'cat_type:{action}:expense' # <-- MODIFIED
            ),
            InlineKeyboardButton(
                t("keyboards.income", context), callback_data=f'cat_type:{action}:income' # <-- MODIFIED
            )
        ],
        [
            InlineKeyboardButton(
                t("keyboards.back", context), callback_data='settings_manage_categories' # <-- MODIFIED
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def iou_menu_keyboard(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(t("keyboards.iou_lent", context), callback_data='iou_lent')], # <-- MODIFIED
        [InlineKeyboardButton(t("keyboards.iou_borrowed", context), # <-- MODIFIED
                              callback_data='iou_borrowed')],
        [InlineKeyboardButton(t("keyboards.iou_view_open", context), callback_data='iou_view')], # <-- MODIFIED
        [InlineKeyboardButton(t("keyboards.iou_view_settled", context), # <-- MODIFIED
                              callback_data='iou_view_settled')],
        [InlineKeyboardButton(t("keyboards.iou_analysis", context), # <-- MODIFIED
                              callback_data='debt_analysis')],
        [InlineKeyboardButton(t("keyboards.back_to_main", context), callback_data='start')], # <-- MODIFIED
    ]
    return InlineKeyboardMarkup(keyboard)


def iou_list_keyboard(grouped_debts, context: ContextTypes.DEFAULT_TYPE,
                      is_settled=False):
    """Shows a consolidated list of debts grouped by person."""
    keyboard = []
    status_str = "settled" if is_settled else "open"

    mode, currencies = _get_user_settings_for_keyboards(context)

    lent = [d for d in grouped_debts if d['type'] == 'lent']
    borrowed = [d for d in grouped_debts if d['type'] == 'borrowed']

    def format_totals(totals):
        parts = []
        for t in totals:
            # Only show totals for currencies the user cares about
            if t['currency'] in currencies:
                amount_format = ",.0f" if t['currency'] == 'KHR' else ",.2f"
                parts.append(
                    f"{t['total']:{amount_format}} {t['currency']} ({t['count']})"
                )
        return ", ".join(parts) if parts else None

    if lent:
        for debt in lent:
            formatted_total = format_totals(debt['totals'])
            if formatted_total: # Only show if there's a relevant total
                label = t("keyboards.iou_person_lent", context, person=debt['person'], totals=formatted_total) # <-- MODIFIED
                keyboard.append(
                    [InlineKeyboardButton(
                        label,
                        callback_data=f"iou:person:{status_str}:{debt['person']}"
                    )]
                )
    if borrowed:
        for debt in borrowed:
            formatted_total = format_totals(debt['totals'])
            if formatted_total: # Only show if there's a relevant total
                label = t("keyboards.iou_person_borrowed", context, person=debt['person'], totals=formatted_total) # <-- MODIFIED
                keyboard.append(
                    [InlineKeyboardButton(
                        label,
                        callback_data=f"iou:person:{status_str}:{debt['person']}"
                    )]
                )

    keyboard.append([InlineKeyboardButton(t("keyboards.back", context), callback_data='iou_menu')]) # <-- MODIFIED
    return InlineKeyboardMarkup(keyboard)


def iou_person_actions_keyboard(person_name, debt_type,
                                context: ContextTypes.DEFAULT_TYPE,
                                is_settled=False):
    """Shows action buttons for the unified person ledger screen."""
    keyboard = []

    if not is_settled:
        keyboard.append([
            InlineKeyboardButton(
                t("keyboards.iou_record_repayment", context), # <-- MODIFIED
                callback_data=f"iou:repay:{person_name}:{debt_type}"
            ),
            InlineKeyboardButton(
                t("keyboards.iou_manage_individual", context), # <-- MODIFIED
                callback_data=f"iou:manage:list:{person_name}:{debt_type}:False"
            )
        ])

    back_callback = 'iou_view_settled' if is_settled else 'iou_view'
    keyboard.append([InlineKeyboardButton(
        t("keyboards.back_to_summary", context), callback_data=back_callback # <-- MODIFIED
    )])
    return InlineKeyboardMarkup(keyboard)


def iou_manage_list_keyboard(person_debts, person_name,
                             debt_type, is_settled,
                             context: ContextTypes.DEFAULT_TYPE):
    """Displays a list of individual debts for management (Edit/Cancel)."""
    keyboard = []

    mode, currencies = _get_user_settings_for_keyboards(context)

    for debt in person_debts:
        # Filter list by user's currency mode
        if debt.get('currency') not in currencies:
            continue

        created_date = datetime.fromisoformat(
            debt['created_at']
        ).strftime('%d %b')
        purpose = debt.get('purpose') or 'No purpose'
        amount_key = 'remainingAmount' if not is_settled else 'originalAmount'
        amount = debt.get(amount_key, 0)
        currency = debt.get('currency')

        amount_format = ",.0f" if currency == 'KHR' else ",.2f"
        label = f"{amount:{amount_format}} {currency} " \
                f"({created_date}) - {purpose}"

        callback = f"iou:detail:{debt['_id']}:{person_name}:{is_settled}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback)])

    back_callback = (
        f"iou:person:settled:{person_name}"
        if is_settled
        else f"iou:person:open:{person_name}"
    )
    keyboard.append([InlineKeyboardButton(
        t("keyboards.back_to_ledger", context), callback_data=back_callback # <-- MODIFIED
    )])
    return InlineKeyboardMarkup(keyboard)


def iou_detail_actions_keyboard(debt_id, person_name, debt_type,
                                is_settled, status,
                                context: ContextTypes.DEFAULT_TYPE):
    """Shows actions for a single, specific debt."""
    keyboard = []

    if status == 'open':
        keyboard.append([
            InlineKeyboardButton(
                t("keyboards.iou_edit_cancel", context), # <-- MODIFIED
                callback_data=f"iou:manage:detail:{debt_id}:{person_name}:"
                              f"{is_settled}"
            )
        ])

    back_callback = f"iou:manage:list:{person_name}:{debt_type}:{is_settled}"
    keyboard.append([InlineKeyboardButton(
        t("keyboards.back_to_list", context), callback_data=back_callback # <-- MODIFIED
    )])
    return InlineKeyboardMarkup(keyboard)


def iou_manage_keyboard(debt_id, person, is_settled_str,
                        context: ContextTypes.DEFAULT_TYPE):
    """Keyboard for editing or canceling a debt."""
    keyboard = [
        [
            InlineKeyboardButton(
                t("keyboards.iou_edit_person", context), callback_data=f"iou:edit:person:{debt_id}" # <-- MODIFIED
            ),
            InlineKeyboardButton(
                t("keyboards.iou_edit_purpose", context), callback_data=f"iou:edit:purpose:{debt_id}" # <-- MODIFIED
            )
        ],
        [
            InlineKeyboardButton(
                t("keyboards.iou_cancel_debt", context), # <-- MODIFIED
                callback_data=f"iou:cancel:prompt:{debt_id}:{person}:"
                              f"{is_settled_str}"
            )
        ],
        [
            InlineKeyboardButton(
                t("keyboards.back", context), # <-- MODIFIED
                callback_data=f"iou:detail:{debt_id}:{person}:{is_settled_str}"
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def iou_cancel_confirm_keyboard(debt_id, person, is_settled_str,
                                context: ContextTypes.DEFAULT_TYPE):
    """Confirmation keyboard for canceling a debt."""
    keyboard = [
        [
            InlineKeyboardButton(
                t("keyboards.iou_cancel_confirm", context), # <-- MODIFIED
                callback_data=f"iou:cancel:confirm:{debt_id}"
            )
        ],
        [
            InlineKeyboardButton(
                t("keyboards.iou_cancel_go_back", context), # <-- MODIFIED
                callback_data=f"iou:manage:detail:{debt_id}:{person}:"
                              f"{is_settled_str}"
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def currency_keyboard(context: ContextTypes.DEFAULT_TYPE):
    """
    Returns a currency keyboard, always showing USD and KHR.
This is only used in dual-currency mode.
    """
    keyboard = [
        [
            InlineKeyboardButton("💵 USD", callback_data='curr_USD'),
            InlineKeyboardButton("៛ KHR", callback_data='curr_KHR')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def expense_categories_keyboard(categories: list,
                                context: ContextTypes.DEFAULT_TYPE):
    """Builds a dynamic keyboard from the user's category list."""
    keyboard = []
    row = []
    for category in categories:
        row.append(
            InlineKeyboardButton(category, callback_data=f'cat_{category}')
        )
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:  # Add any remaining buttons
        keyboard.append(row)

    # Add the static "Other" button
    keyboard.append([
        InlineKeyboardButton(
            t("keyboards.other", context), callback_data='cat_other'
        )
    ])
    return InlineKeyboardMarkup(keyboard)


def income_categories_keyboard(categories: list,
                               context: ContextTypes.DEFAULT_TYPE):
    """Builds a dynamic keyboard from the user's category list."""
    keyboard = []
    row = []
    for category in categories:
        row.append(
            InlineKeyboardButton(category, callback_data=f'cat_{category}')
        )
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:  # Add any remaining buttons
        keyboard.append(row)

    # Add the static "Other" button
    keyboard.append([
        InlineKeyboardButton(
            t("keyboards.other", context), callback_data='cat_other'
        )
    ])
    return InlineKeyboardMarkup(keyboard)


def ask_remark_keyboard(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.add_remark", context), callback_data='remark_yes'), # <-- MODIFIED
            InlineKeyboardButton(t("keyboards.skip", context), callback_data='remark_no') # <-- MODIFIED
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def history_keyboard(transactions, context: ContextTypes.DEFAULT_TYPE,
                     is_search_result=False):
    keyboard = []
    if not is_search_result:
        keyboard.append([InlineKeyboardButton(
            t("keyboards.search", context), callback_data='search_menu'
        )])

    mode, currencies = _get_user_settings_for_keyboards(context)

    for tx in transactions:
        # Filter list by user's currency mode
        if tx.get('currency') not in currencies:
            continue

        amount = tx.get('amount', 0)
        currency = tx.get('currency', 'N/A')
        category = tx.get('categoryId', 'Unknown')
        tx_type_emoji = "⬇️" if tx.get('type') == 'expense' else "⬆️"

        amount_format = ",.0f" if currency == 'KHR' else ",.2f"
        label = f"{tx_type_emoji} {amount:{amount_format}} " \
                f"{currency} - {category}"
        callback = f"manage_tx_{tx['_id']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback)])

    keyboard.append([InlineKeyboardButton(
        t("keyboards.back_to_main", context), callback_data='start' # <-- MODIFIED
    )])
    return InlineKeyboardMarkup(keyboard)


def manage_tx_keyboard(tx_id, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.edit", context), callback_data=f'edit_tx_{tx_id}'), # <-- MODIFIED
            InlineKeyboardButton(t("keyboards.delete", context), # <-- MODIFIED
                                 callback_data=f'delete_tx_{tx_id}')
        ],
        [InlineKeyboardButton(t("keyboards.back_to_history", context), callback_data='history')], # <-- MODIFIED
    ]
    return InlineKeyboardMarkup(keyboard)


def edit_tx_options_keyboard(tx_id, context: ContextTypes.DEFAULT_TYPE):

    mode, currencies = _get_user_settings_for_keyboards(context)

    keyboard = [
        [
            InlineKeyboardButton(
                t("keyboards.edit_amount", context), callback_data=f'edit_field_amount_{tx_id}' # <-- MODIFIED
            ),
            InlineKeyboardButton(
                t("keyboards.edit_category", context), callback_data=f'edit_field_categoryId_{tx_id}' # <-- MODIFIED
            ),
        ],
        [
            InlineKeyboardButton(
                t("keyboards.edit_description", context), # <-- MODIFIED
                callback_data=f'edit_field_description_{tx_id}'
            ),
            InlineKeyboardButton(
                t("keyboards.edit_date", context), callback_data=f'edit_field_timestamp_{tx_id}' # <-- MODIFIED
            ),
        ],
    ]

    # Only show the "Edit Currency" button to dual-mode users
    if mode == 'dual':
        keyboard.append([
            InlineKeyboardButton(
                t("keyboards.edit_currency", context), callback_data=f'edit_field_currency_{tx_id}' # <-- MODIFIED
            )
        ])

    keyboard.append([InlineKeyboardButton(
        t("keyboards.edit_cancel", context), callback_data=f'manage_tx_{tx_id}' # <-- MODIFIED
    )])

    return InlineKeyboardMarkup(keyboard)


def confirm_delete_keyboard(tx_id, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(t("keyboards.delete_confirm", context), # <-- MODIFIED
                                 callback_data=f'confirm_delete_{tx_id}'),
            InlineKeyboardButton(t("keyboards.delete_cancel", context), # <-- MODIFIED
                                 callback_data=f'manage_tx_{tx_id}')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- End of modified file ---