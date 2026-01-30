# telegram_bot/keyboards/utils.py

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