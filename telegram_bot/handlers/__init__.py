# --- Start of corrected file: telegram_bot/handlers/__init__.py ---

from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from .common import start, quick_check, cancel, search_menu
from .analytics import (
    report_menu, process_report_choice, received_report_start_date, received_report_end_date,
    habits_menu, process_habits_choice,
    CHOOSE_REPORT_PERIOD, REPORT_ASK_START_DATE, REPORT_ASK_END_DATE, CHOOSE_HABITS_PERIOD
)
from .iou import (
    iou_menu, iou_view, iou_person_detail, iou_detail, debt_analysis,
    iou_start, iou_received_date_choice, iou_received_custom_date, iou_received_person,
    iou_received_amount, iou_received_currency, iou_received_purpose,
    repay_lump_start, received_lump_repayment_amount,
    IOU_ASK_DATE, IOU_CUSTOM_DATE, IOU_PERSON, IOU_AMOUNT, IOU_CURRENCY, IOU_PURPOSE, REPAY_LUMP_AMOUNT
)
from .transaction import (
    add_transaction_start, forgot_log_start, received_forgot_day, received_forgot_custom_date,
    received_forgot_type, received_amount, received_currency, received_category,
    received_custom_category, ask_remark, received_remark, save_transaction_and_end,
    history_menu, manage_transaction, delete_transaction_prompt, delete_transaction_confirm,
    edit_transaction_start, edit_choose_field, edit_received_new_value, edit_received_new_category,
    edit_received_custom_category,
    # --- FIX: Import new date handler and state ---
    edit_received_new_date, EDIT_GET_NEW_DATE,
    # --- End Fix ---
    AMOUNT, CURRENCY, CATEGORY, CUSTOM_CATEGORY, ASK_REMARK, REMARK,
    FORGOT_DATE, FORGOT_CUSTOM_DATE, FORGOT_TYPE,
    EDIT_CHOOSE_FIELD, EDIT_GET_NEW_VALUE, EDIT_GET_NEW_CATEGORY, EDIT_GET_CUSTOM_CATEGORY
)
from .utility import (
    update_rate_start, received_new_rate, set_balance_start, received_balance_account,
    received_balance_amount, set_reminder_start, received_reminder_purpose,
    received_reminder_date_choice, received_reminder_custom_date, received_reminder_time,
    NEW_RATE, SETBALANCE_ACCOUNT, SETBALANCE_AMOUNT,
    REMINDER_PURPOSE, REMINDER_ASK_DATE, REMINDER_CUSTOM_DATE, REMINDER_ASK_TIME
)
from .search import (
    search_start, received_period_choice, received_custom_start, received_custom_end,
    received_type_choice, received_categories, received_keywords, received_keyword_logic,
    CHOOSE_PERIOD, GET_CUSTOM_START, GET_CUSTOM_END, CHOOSE_TYPE,
    GET_CATEGORIES, GET_KEYWORDS, GET_KEYWORD_LOGIC
)

# --- Build Conversation Handlers ---

tx_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(add_transaction_start, pattern='^(add_expense|add_income)$')],
    states={
        AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_amount)],
        CURRENCY: [CallbackQueryHandler(received_currency, pattern='^curr_')],
        CATEGORY: [CallbackQueryHandler(received_category, pattern='^cat_')],
        CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_custom_category)],
        ASK_REMARK: [CallbackQueryHandler(ask_remark, pattern='^remark_')],
        REMARK: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_remark)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_message=False
)

forgot_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(forgot_log_start, pattern='^forgot_log_start$')],
    states={
        FORGOT_DATE: [CallbackQueryHandler(received_forgot_day, pattern='^forgot_day_')],
        FORGOT_CUSTOM_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_forgot_custom_date)],
        FORGOT_TYPE: [CallbackQueryHandler(received_forgot_type, pattern='^forgot_type_')],
        AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_amount)],
        CURRENCY: [CallbackQueryHandler(received_currency, pattern='^curr_')],
        CATEGORY: [CallbackQueryHandler(received_category, pattern='^cat_')],
        CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_custom_category)],
        ASK_REMARK: [CallbackQueryHandler(ask_remark, pattern='^remark_')],
        REMARK: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_remark)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_message=False
)

edit_tx_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(edit_transaction_start, pattern='^edit_tx_')],
    states={
        EDIT_CHOOSE_FIELD: [CallbackQueryHandler(edit_choose_field, pattern='^edit_field_')],
        EDIT_GET_NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_received_new_value)],
        EDIT_GET_NEW_CATEGORY: [CallbackQueryHandler(edit_received_new_category, pattern='^cat_')],
        EDIT_GET_CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_received_custom_category)],
        # --- FIX: Add new state for date editing ---
        EDIT_GET_NEW_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_received_new_date)],
        # --- End Fix ---
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_message=False
)

iou_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(iou_start, pattern='^(iou_lent|iou_borrowed)$')],
    states={
        IOU_ASK_DATE: [CallbackQueryHandler(iou_received_date_choice, pattern='^iou_date_')],
        IOU_CUSTOM_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_custom_date)],
        IOU_PERSON: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_person)],
        IOU_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_amount)],
        IOU_CURRENCY: [CallbackQueryHandler(iou_received_currency, pattern='^curr_')],
        IOU_PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, iou_received_purpose)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_message=False
)

repay_lump_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(repay_lump_start, pattern='^iou:repay:')],
    states={
        REPAY_LUMP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_lump_repayment_amount)]
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_message=False
)

rate_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(update_rate_start, pattern='^update_rate$')],
    states={NEW_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_new_rate)]},
    fallbacks=[CommandHandler('cancel', cancel)],
    per_message=False
)

set_balance_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(set_balance_start, pattern='^set_balance_start$')],
    states={
        SETBALANCE_ACCOUNT: [CallbackQueryHandler(received_balance_account, pattern='^set_balance_')],
        SETBALANCE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_balance_amount)]
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_message=False
)

reminder_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(set_reminder_start, pattern='^set_reminder_start$')],
    states={
        REMINDER_PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_reminder_purpose)],
        REMINDER_ASK_DATE: [CallbackQueryHandler(received_reminder_date_choice, pattern='^remind_date_')],
        REMINDER_CUSTOM_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_reminder_custom_date)],
        REMINDER_ASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_reminder_time)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_message=False
)

report_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(report_menu, pattern='^report_menu$')],
    states={
        CHOOSE_REPORT_PERIOD: [CallbackQueryHandler(process_report_choice, pattern='^report_period_')],
        REPORT_ASK_START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_report_start_date)],
        REPORT_ASK_END_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_report_end_date)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_message=False
)

habits_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(habits_menu, pattern='^habits_menu$')],
    states={
        CHOOSE_HABITS_PERIOD: [CallbackQueryHandler(process_habits_choice, pattern='^report_period_')]
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_message=False
)

search_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(search_start, pattern='^start_search_')],
    states={
        CHOOSE_PERIOD: [CallbackQueryHandler(received_period_choice, pattern='^report_period_')],
        GET_CUSTOM_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_custom_start)],
        GET_CUSTOM_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_custom_end)],
        CHOOSE_TYPE: [CallbackQueryHandler(received_type_choice, pattern='^search_type_')],
        GET_CATEGORIES: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, received_categories),
            CallbackQueryHandler(received_categories, pattern='^search_skip_categories$')
        ],
        GET_KEYWORDS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, received_keywords),
            CallbackQueryHandler(received_keywords, pattern='^search_skip_keywords$')
        ],
        GET_KEYWORD_LOGIC: [CallbackQueryHandler(received_keyword_logic, pattern='^search_logic_')],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_message=False
)