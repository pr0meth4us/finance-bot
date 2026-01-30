# telegram_bot/keyboards/iou.py

from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.i18n import t
from .utils import _get_mode_and_currencies

def iou_menu_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("keyboards.iou_lent", context), callback_data='iou_lent')],
        [InlineKeyboardButton(t("keyboards.iou_borrowed", context), callback_data='iou_borrowed')],
        [InlineKeyboardButton(t("keyboards.iou_view_open", context), callback_data='iou_view')],
        [InlineKeyboardButton(t("keyboards.iou_view_settled", context), callback_data='iou_view_settled')],
        [InlineKeyboardButton(t("keyboards.iou_analysis", context), callback_data='debt_analysis')],
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