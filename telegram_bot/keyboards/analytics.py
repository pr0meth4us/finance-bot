# telegram_bot/keyboards/analytics.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.i18n import t

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

    keyboard.append([InlineKeyboardButton(t("keyboards.back", context), callback_data='menu')])
    return InlineKeyboardMarkup(keyboard)


def search_menu_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("keyboards.search_manage", context), callback_data='start_search_manage')],
        [InlineKeyboardButton(t("keyboards.search_sum", context), callback_data='start_search_sum')],
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
        [InlineKeyboardButton(t("keyboards.back_to_main", context), callback_data='menu')],
    ])