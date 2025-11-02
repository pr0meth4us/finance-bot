import os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from dotenv import load_dotenv
# --- MODIFICATION START ---
from handlers import (
    start, quick_check, search_menu, cancel,
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
    # --- NEW: Import new handlers ---
    iou_view_settled, iou_person_detail_settled,
    iou_manage_menu, iou_cancel_prompt, iou_cancel_confirm,
    iou_edit_conversation_handler
    # --- End New ---
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

    # 1. System command handlers for start/cancel and specific commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))

    # --- MODIFICATION START: Reorder handlers ---
    # 2. Add button-based conversation handlers FIRST.
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
    app.add_handler(iou_edit_conversation_handler) # --- NEW: Add edit handler ---

    # 3. The unified message handler should be one of the LAST handlers.
    app.add_handler(unified_message_conversation_handler)
    # --- MODIFICATION END ---

    # 4. Standalone callback handlers for specific button presses.
    app.add_handler(CallbackQueryHandler(start, pattern='^start$'))
    app.add_handler(CallbackQueryHandler(quick_check, pattern='^quick_check$'))
    app.add_handler(CallbackQueryHandler(search_menu, pattern='^search_menu$'))
    app.add_handler(CallbackQueryHandler(history_menu, pattern='^history$'))
    app.add_handler(CallbackQueryHandler(manage_transaction, pattern='^manage_tx_'))
    app.add_handler(CallbackQueryHandler(delete_transaction_prompt, pattern='^delete_tx_'))
    app.add_handler(CallbackQueryHandler(delete_transaction_confirm, pattern='^confirm_delete_'))

    # --- NEW: Add IOU CRUD handlers ---
    app.add_handler(CallbackQueryHandler(iou_menu, pattern='^iou_menu$'))
    app.add_handler(CallbackQueryHandler(iou_view, pattern='^iou_view$'))
    app.add_handler(CallbackQueryHandler(iou_view_settled, pattern='^iou_view_settled$'))
    app.add_handler(CallbackQueryHandler(iou_person_detail, pattern='^iou:person:open:'))
    app.add_handler(CallbackQueryHandler(iou_person_detail_settled, pattern='^iou:person:settled:'))
    app.add_handler(CallbackQueryHandler(iou_detail, pattern='^iou:detail:'))
    app.add_handler(CallbackQueryHandler(iou_manage_menu, pattern='^iou:manage:'))
    app.add_handler(CallbackQueryHandler(iou_cancel_prompt, pattern='^iou:cancel:prompt:'))
    app.add_handler(CallbackQueryHandler(iou_cancel_confirm, pattern='^iou:cancel:confirm:'))
    app.add_handler(CallbackQueryHandler(debt_analysis, pattern='^debt_analysis$'))
    # --- End New ---

    print("🚀 Bot is running...")
    app.run_polling()


if __name__ == '__main__':
    main()