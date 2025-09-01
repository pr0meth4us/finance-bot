import os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from dotenv import load_dotenv
from . import handlers

load_dotenv()

def main():
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        print("❌ TELEGRAM_TOKEN not found in .env file.")
        return

    app = Application.builder().token(TOKEN).build()

    # --- Register Handlers ---
    app.add_handler(handlers.tx_conversation_handler)
    app.add_handler(handlers.rate_conversation_handler)
    app.add_handler(handlers.iou_conversation_handler)

    app.add_handler(CommandHandler("start", handlers.start))

    # Callbacks for main menu and other features
    app.add_handler(CallbackQueryHandler(handlers.start, pattern='^start$'))
    app.add_handler(CallbackQueryHandler(handlers.get_report, pattern='^report$'))

    # History callbacks
    app.add_handler(CallbackQueryHandler(handlers.history_menu, pattern='^history$'))
    app.add_handler(CallbackQueryHandler(handlers.manage_transaction, pattern='^manage_tx_'))
    app.add_handler(CallbackQueryHandler(handlers.delete_transaction_prompt, pattern='^delete_tx_'))
    app.add_handler(CallbackQueryHandler(handlers.delete_transaction_confirm, pattern='^confirm_delete_'))

    # IOU callbacks
    app.add_handler(CallbackQueryHandler(handlers.iou_menu, pattern='^iou_menu$'))
    app.add_handler(CallbackQueryHandler(handlers.iou_view, pattern='^iou_view$'))
    app.add_handler(CallbackQueryHandler(handlers.iou_settle, pattern='^settle_debt_'))

    print("🚀 Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()