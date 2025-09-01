import os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from dotenv import load_dotenv
import handlers

load_dotenv()


def main():
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        print("❌ TELEGRAM_TOKEN not found in .env file.")
        return

    app = Application.builder().token(TOKEN).build()

    # --- Register Conversation Handlers ---
    app.add_handler(handlers.tx_conversation_handler)
    app.add_handler(handlers.rate_conversation_handler)
    app.add_handler(handlers.iou_conversation_handler)
    app.add_handler(handlers.repay_conversation_handler)
    app.add_handler(handlers.set_balance_conversation_handler)

    # --- Register Standalone Command Handlers ---
    app.add_handler(CommandHandler("start", handlers.start))

    # --- Register Standalone Callback Query Handlers ---
    app.add_handler(CallbackQueryHandler(handlers.start, pattern='^start$'))
    app.add_handler(CallbackQueryHandler(handlers.report_menu, pattern='^report_menu$'))
    app.add_handler(CallbackQueryHandler(handlers.generate_report_for_period, pattern='^report_period_'))

    # History callbacks
    app.add_handler(CallbackQueryHandler(handlers.history_menu, pattern='^history$'))
    app.add_handler(CallbackQueryHandler(handlers.manage_transaction, pattern='^manage_tx_'))
    app.add_handler(CallbackQueryHandler(handlers.delete_transaction_prompt, pattern='^delete_tx_'))
    app.add_handler(CallbackQueryHandler(handlers.delete_transaction_confirm, pattern='^confirm_delete_'))

    # IOU callbacks
    app.add_handler(CallbackQueryHandler(handlers.iou_menu, pattern='^iou_menu$'))
    app.add_handler(CallbackQueryHandler(handlers.iou_view, pattern='^iou_view$'))
    app.add_handler(CallbackQueryHandler(handlers.iou_detail, pattern='^iou_detail_'))

    print("🚀 Bot is running...")
    app.run_polling()


if __name__ == '__main__':
    main()