import os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from dotenv import load_dotenv
# --- MODIFICATION START ---
from handlers import (
    start, quick_check, cancel,
    tx_conversation_handler,
    rate_conversation_handler,
    iou_conversation_handler,
    repay_lump_conversation_handler,
    set_balance_conversation_handler,
    forgot_conversation_handler,
    reminder_conversation_handler,
    report_conversation_handler,
    edit_tx_conversation_handler,
    habits_conversation_handler,
    search_conversation_handler,
    history_menu, manage_transaction, delete_transaction_prompt, delete_transaction_confirm,
    iou_menu, iou_view, iou_person_detail, iou_detail, debt_analysis,
    iou_view_settled, iou_person_detail_settled, iou_manage_list,
    iou_manage_menu, iou_cancel_prompt, iou_cancel_confirm,
    iou_edit_conversation_handler,
    get_current_rate,
    # New command handlers for menus
    add_transaction_start, forgot_log_start,
    search_menu_entry, report_menu, habits_menu,
    update_rate_start, get_current_rate as get_current_rate_cmd, set_balance_start, set_reminder_start,
    iou_start, iou_view as iou_view_open_cmd, iou_view_settled as iou_view_settled_cmd,
    debt_analysis as debt_analysis_cmd,
    search_start as search_start_cmd
)
from handlers.command_handler import unified_message_conversation_handler
# --- MODIFICATION END ---

load_dotenv()


def main():
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        print("❌ TELEGRAM_TOKEN not found in .env file.")
        return

    app = Application.builder().token(TOKEN).build()

    # --- Register ALL Handlers ---

    # 1. System command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))

    # 2. Add conversation handlers
    app.add_handler(tx_conversation_handler)
    app.add_handler(rate_conversation_handler)
    app.add_handler(iou_conversation_handler)
    app.add_handler(repay_lump_conversation_handler)
    app.add_handler(set_balance_conversation_handler)
    app.add_handler(forgot_conversation_handler)
    app.add_handler(reminder_conversation_handler)
    app.add_handler(report_conversation_handler)
    app.add_handler(edit_tx_conversation_handler)
    app.add_handler(habits_conversation_handler)
    app.add_handler(search_conversation_handler)
    app.add_handler(iou_edit_conversation_handler)

    # 3. Add standalone command handlers (for menus)
    app.add_handler(CommandHandler("quick_check", quick_check))
    app.add_handler(CommandHandler("history", history_menu))
    app.add_handler(CommandHandler("iou", iou_menu))
    app.add_handler(CommandHandler("get_rate", get_current_rate_cmd))

    # --- Re-add handlers for conversations started by commands ---
    # These are needed because they are also entry_points in ConversationHandlers
    app.add_handler(CommandHandler("add_expense", add_transaction_start))
    app.add_handler(CommandHandler("add_income", add_transaction_start))
    app.add_handler(CommandHandler("forgot", forgot_log_start))
    app.add_handler(CommandHandler("search", search_menu_entry))
    app.add_handler(CommandHandler("search_manage", search_start_cmd))
    app.add_handler(CommandHandler("search_sum", search_start_cmd))
    app.add_handler(CommandHandler("report", report_menu))
    app.add_handler(CommandHandler("habits", habits_menu))
    app.add_handler(CommandHandler("rate", update_rate_start))
    app.add_handler(CommandHandler("balance", set_balance_start))
    app.add_handler(CommandHandler("reminder", set_reminder_start))
    app.add_handler(CommandHandler("iou_lent", iou_start))
    app.add_handler(CommandHandler("iou_borrowed", iou_start))
    app.add_handler(CommandHandler("iou_view_open", iou_view_open_cmd))
    app.add_handler(CommandHandler("iou_view_settled", iou_view_settled_cmd))
    app.add_handler(CommandHandler("iou_analysis", debt_analysis_cmd))

    # 4. The unified message handler (for '!' commands)
    app.add_handler(unified_message_conversation_handler)

    # 5. Standalone callback handlers for dynamic inline buttons
    # These MUST remain as CallbackQueryHandlers
    app.add_handler(CallbackQueryHandler(manage_transaction, pattern='^manage_tx_'))
    app.add_handler(CallbackQueryHandler(delete_transaction_prompt, pattern='^delete_tx_'))
    app.add_handler(CallbackQueryHandler(delete_transaction_confirm, pattern='^confirm_delete_'))

    app.add_handler(CallbackQueryHandler(iou_person_detail, pattern='^iou:person:open:'))
    app.add_handler(CallbackQueryHandler(iou_person_detail_settled, pattern='^iou:person:settled:'))
    app.add_handler(CallbackQueryHandler(iou_detail, pattern='^iou:detail:'))
    app.add_handler(CallbackQueryHandler(iou_manage_list, pattern='^iou:manage:list:'))
    app.add_handler(CallbackQueryHandler(iou_manage_menu, pattern='^iou:manage:detail:'))
    app.add_handler(CallbackQueryHandler(iou_cancel_prompt, pattern='^iou:cancel:prompt:'))
    app.add_handler(CallbackQueryHandler(iou_cancel_confirm, pattern='^iou:cancel:confirm:'))

    print("🚀 Bot is running...")
    app.run_polling()


if __name__ == '__main__':
    main()