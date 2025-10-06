import os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from dotenv import load_dotenv
from handlers import (
    # Common handlers
    start, quick_check,
    # Generic Commands
    generic_transaction_handler, generic_debt_handler,
    # Conversation handlers
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
    unified_command_conversation_handler,
    # Standalone callback handlers
    history_menu, manage_transaction, delete_transaction_prompt, delete_transaction_confirm,
    iou_menu, iou_view, iou_person_detail, iou_detail, debt_analysis,
)

load_dotenv()

def main():
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        print("❌ TELEGRAM_TOKEN not found in .env file.")
        return

    app = Application.builder().token(TOKEN).build()
    
    # --- Register Command Handlers ---
    # Specific, multi-argument commands are registered first to be checked first.
    app.add_handler(CommandHandler(["expense", "income"], generic_transaction_handler))
    app.add_handler(CommandHandler(["lent", "borrowed"], generic_debt_handler))

    # The unified handler for quick/smart commands is a ConversationHandler
    # and will catch any command NOT handled by the ones above.
    app.add_handler(unified_command_conversation_handler)
    
    # --- Register Other Conversation Handlers ---
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

    # --- Register Standalone Command Handlers ---
    app.add_handler(CommandHandler("start", start))

    # --- Register Standalone Callback Query Handlers ---
    app.add_handler(CallbackQueryHandler(start, pattern='^start$'))
    app.add_handler(CallbackQueryHandler(quick_check, pattern='^quick_check$'))

    # Transaction History & Management
    app.add_handler(CallbackQueryHandler(history_menu, pattern='^history$'))
    app.add_handler(CallbackQueryHandler(manage_transaction, pattern='^manage_tx_'))
    app.add_handler(CallbackQueryHandler(delete_transaction_prompt, pattern='^delete_tx_'))
    app.add_handler(CallbackQueryHandler(delete_transaction_confirm, pattern='^confirm_delete_'))

    # IOU / Debt Management
    app.add_handler(CallbackQueryHandler(iou_menu, pattern='^iou_menu$'))
    app.add_handler(CallbackQueryHandler(iou_view, pattern='^iou_view$'))
    app.add_handler(CallbackQueryHandler(iou_person_detail, pattern='^iou:person:'))
    app.add_handler(CallbackQueryHandler(iou_detail, pattern='^iou:detail:'))
    app.add_handler(CallbackQueryHandler(debt_analysis, pattern='^debt_analysis$'))

    print("🚀 Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
