# telegram_bot/keyboards/menus.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.i18n import t

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