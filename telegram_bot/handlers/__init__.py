# --- Start of corrected file: telegram_bot/handlers/__init__.py ---

from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from .common import start, quick_check, cancel
from .analytics import (
    report_menu, process_report_choice, received_report_start_date, received_report_end_date,
    habits_menu, process_habits_choice,
    CHOOSE_REPORT_PERIOD, REPORT_ASK_START_DATE, REPORT_ASK_END_DATE, CHOOSE_HABITS_PERIOD,
    REPORT_PERIOD_REGEX
)
from .iou import (
    iou_menu, iou_view, iou_person_detail, iou_detail, debt_analysis,
    iou_start, iou_received_date_choice, iou_received_custom_date, iou_received_person,
    iou_received_amount, iou_received_currency, iou_received_purpose,
    repay_lump_start, received_lump_repayment_amount,
    iou_view_settled, iou_person_detail_settled, iou_manage_list,
    iou_manage_menu, iou_cancel_prompt, iou_cancel_confirm,
    iou_edit_start, iou_edit_received_value,
    IOU_ASK_DATE, IOU_CUSTOM_DATE, IOU_PERSON, IOU_AMOUNT, IOU_CURRENCY, IOU_PURPOSE, REPAY_LUMP_AMOUNT,
    IOU_EDIT_GET_VALUE,
    IOU_DATE_REGEX, CURRENCY_REGEX as IOU_CURRENCY_REGEX
)
from .transaction import (
    add_transaction_start,
    forgot_log_start, received_forgot_day, received_forgot_custom_date,
    received_forgot_type, received_amount, received_currency, received_category,
    received_custom_category, ask_remark, received_remark, save_transaction_and_end,
    history_menu, manage_transaction, delete_transaction_prompt, delete_transaction_confirm,
    edit_transaction_start, edit_choose_field, edit_received_new_value, edit_received_new_category,
    edit_received_custom_category,
    edit_received_new_date, EDIT_GET_NEW_DATE,
    AMOUNT, CURRENCY, CATEGORY, CUSTOM_CATEGORY, ASK_REMARK, REMARK,
    FORGOT_DATE, FORGOT_CUSTOM_DATE, FORGOT_TYPE,
    EDIT_CHOOSE_FIELD, EDIT_GET_NEW_VALUE, EDIT_GET_NEW_CATEGORY, EDIT_GET_CUSTOM_CATEGORY,
    FORGOT_DAY_REGEX, FORGOT_TYPE_REGEX, CURRENCY_REGEX, CAT_REGEX, REMARK_REGEX
)
from .utility import (
    update_rate_start, received_new_rate, set_balance_start, received_balance_account,
    received_balance_amount, set_reminder_start, received_reminder_purpose,
    received_reminder_date_choice, received_reminder_custom_date, received_reminder_time,
    get_current_rate,
    NEW_RATE, SETBALANCE_ACCOUNT, SETBALANCE_AMOUNT,
    REMINDER_PURPOSE, REMINDER_ASK_DATE, REMINDER_CUSTOM_DATE, REMINDER_ASK_TIME,
    SETBALANCE_ACC_REGEX, REMINDER_DATE_REGEX
)
from .search import (
    search_menu_entry,
    search_start, received_period_choice, received_custom_start, received_custom_end,
    received_type_choice, received_categories, received_keywords, received_keyword_logic,
    CHOOSE_PERIOD, GET_CUSTOM_START, GET_CUSTOM_END, CHOOSE_TYPE,
    GET_CATEGORIES, GET_KEYWORDS, GET_KEYWORD_LOGIC,
    CHOOSE_ACTION,
    REPORT_PERIOD_REGEX as SEARCH_REPORT_PERIOD_REGEX,
    SEARCH_TYPE_REGEX, SKIP_CAT_REGEX, SKIP_KWD_REGEX, LOGIC_REGEX
)

# --- Build Conversation Handlers ---

tx_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('add_expense', add_transaction_start), CommandHandler('add_income', add_transaction_start)],
    states={
        AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_amount)],
        CURRENCY: [MessageHandler(filters.Regex(CURRENCY_REGEX), received_currency)],
        CATEGORY: [MessageHandler(filters.Regex(CAT_REGEX), received_category)],
        CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_custom_category)],
        ASK_REMARK: [MessageHandler(filters.Regex(REMARK_REGEX), ask_remark)],
        REMARK: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_remark)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

forgot_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('forgot', forgot_log_start)],
    states={
        FORGOT_DATE: [MessageHandler(filters.Regex(FORGOT_DAY_REGEX), received_forgot_day)],
        FORGOT_CUSTOM_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_forgot_custom_date)],
        FORGOT_TYPE: [MessageHandler(filters.Regex(FORGOT_TYPE_REGEX), received_forgot_type)],
        AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_amount)],
        CURRENCY: [MessageHandler(filters.Regex(CURRENCY_REGEX), received_currency)],
        CATEGORY: [MessageHandler(filters.Regex(CAT_REGEX), received_category)],
        CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_custom_category)],
        ASK_REMARK: [MessageHandler(filters.Regex(REMARK_REGEX), ask_remark)],
        REMARK: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_remark)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

edit_tx_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(edit_transaction_start, pattern='^edit_tx_')],
    states={
        EDIT_CHOOSE_FIELD: [CallbackQueryHandler(edit_choose_field, pattern='^edit_field_')],
        EDIT_GET_NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_received_new_value)],
        EDIT_GET_NEW_CATEGORY: [CallbackQueryHandler(edit_received_new_category, pattern='^cat_')],
        EDIT_GET_CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_received_custom_category)],
        EDIT_GET_NEW_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_received_new_date)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

iou_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('iou_lent', iou_start), CommandHandler('iou_borrowed', iou_start)],
    states={
        IOU_ASK_DATE: [MessageHandler(filters.Regex(IOU_DATE_REGEX), iou_received_date_choice)],
        IOU_CUSTOM_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_custom_date)],
        IOU_PERSON: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_person)],
        IOU_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_amount)],
        IOU_CURRENCY: [MessageHandler(filters.Regex(IOU_CURRENCY_REGEX), iou_received_currency)],
        IOU_PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_purpose)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

iou_edit_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(iou_edit_start, pattern='^iou:edit:')],
    states={
        IOU_EDIT_GET_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_edit_received_value)]
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

repay_lump_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(repay_lump_start, pattern='^iou:repay:')],
    states={
        REPAY_LUMP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_lump_repayment_amount)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

rate_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('rate', update_rate_start)],
    states={NEW_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_new_rate)]},
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

set_balance_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('balance', set_balance_start)],
    states={
        SETBALANCE_ACCOUNT: [MessageHandler(filters.Regex(SETBALANCE_ACC_REGEX), received_balance_account)],
        SETBALANCE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_balance_amount)]
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

reminder_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('reminder', set_reminder_start)],
    states={
        REMINDER_PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_reminder_purpose)],
        REMINDER_ASK_DATE: [MessageHandler(filters.Regex(REMINDER_DATE_REGEX), received_reminder_date_choice)],
        REMINDER_CUSTOM_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_reminder_custom_date)],
        REMINDER_ASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_reminder_time)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

report_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('report', report_menu)],
    states={
        CHOOSE_REPORT_PERIOD: [MessageHandler(filters.Regex(REPORT_PERIOD_REGEX), process_report_choice)],
        REPORT_ASK_START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_report_start_date)],
        REPORT_ASK_END_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_report_end_date)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

habits_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('habits', habits_menu)],
    states={
        CHOOSE_HABITS_PERIOD: [MessageHandler(filters.Regex(REPORT_PERIOD_REGEX), process_habits_choice)]
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)

search_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('search', search_menu_entry)],
    states={
        CHOOSE_ACTION: [CommandHandler(['search_manage', 'search_sum'], search_start)],
        CHOOSE_PERIOD: [MessageHandler(filters.Regex(SEARCH_REPORT_PERIOD_REGEX), received_period_choice)],
        GET_CUSTOM_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_custom_start)],
        GET_CUSTOM_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_custom_end)],
        CHOOSE_TYPE: [MessageHandler(filters.Regex(SEARCH_TYPE_REGEX), received_type_choice)],
        GET_CATEGORIES: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, received_categories),
            MessageHandler(filters.Regex(SKIP_CAT_REGEX), received_categories)
        ],
        GET_KEYWORDS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, received_keywords),
            MessageHandler(filters.Regex(SKIP_KWD_REGEX), received_keywords)
        ],
        GET_KEYWORD_LOGIC: [MessageHandler(filters.Regex(LOGIC_REGEX), received_keyword_logic)],
    },
    fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    per_message=False
)