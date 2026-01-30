# telegram_bot/keyboards/settings.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.i18n import t
from .utils import _get_mode_and_currencies

def settings_menu_keyboard(context: ContextTypes.DEFAULT_TYPE):
    mode, _ = _get_mode_and_currencies(context)

    keyboard = [
        [InlineKeyboardButton(t("keyboards.settings_update_balances", context), callback_data='settings_set_balance')],
        [InlineKeyboardButton(t("keyboards.settings_manage_categories", context),
                              callback_data='settings_manage_categories')],
        [InlineKeyboardButton(t("keyboards.settings_change_language", context),
                              callback_data='settings_change_language')],
        [InlineKeyboardButton(t("keyboards.settings_link_email", context), callback_data='settings_link_email')],
    ]

    if mode == 'dual':
        keyboard.append(
            [InlineKeyboardButton(t("keyboards.settings_update_rate", context), callback_data='settings_set_rate')])
    elif mode == 'single':
        keyboard.append([InlineKeyboardButton(t("keyboards.settings_switch_to_dual", context),
                                              callback_data='settings_switch_to_dual')])

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


def subscription_tier_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("keyboards.plan_free", context), callback_data='plan_free')],
        [InlineKeyboardButton(t("keyboards.plan_premium", context), callback_data='plan_premium')],
    ])