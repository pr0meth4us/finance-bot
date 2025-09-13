# --- Start of modified file: telegram_bot/bot.py ---

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
    app.add_handler(handlers.repay_lump_conversation_handler)
    app.add_handler(handlers.set_balance_conversation_handler)
    app.add_handler(handlers.forgot_conversation_handler)
    app.add_handler(handlers.reminder_conversation_handler)
    app.add_handler(handlers.report_conversation_handler)
    # --- START OF MODIFICATION ---
    # Add the new conversation handler for editing transactions
    app.add_handler(handlers.edit_tx_conversation_handler)
    # --- END OF MODIFICATION ---

    # --- Register Standalone Command Handlers ---
    app.add_handler(CommandHandler("start", handlers.start))

    # --- Register Standalone Callback Query Handlers ---
    app.add_handler(CallbackQueryHandler(handlers.start, pattern='^start$'))
    app.add_handler(CallbackQueryHandler(handlers.quick_check, pattern='^quick_check$'))

    # History callbacks
    app.add_handler(CallbackQueryHandler(handlers.history_menu, pattern='^history$'))
    app.add_handler(CallbackQueryHandler(handlers.manage_transaction, pattern='^manage_tx_'))
    app.add_handler(CallbackQueryHandler(handlers.delete_transaction_prompt, pattern='^delete_tx_'))
    app.add_handler(CallbackQueryHandler(handlers.delete_transaction_confirm, pattern='^confirm_delete_'))

    # IOU callbacks (New flow)
    app.add_handler(CallbackQueryHandler(handlers.iou_menu, pattern='^iou_menu$'))
    app.add_handler(CallbackQueryHandler(handlers.iou_view, pattern='^iou_view$'))
    app.add_handler(CallbackQueryHandler(handlers.iou_person_detail, pattern='^iou:person:'))
    app.add_handler(CallbackQueryHandler(handlers.iou_detail, pattern='^iou:detail:'))


    print("🚀 Bot is running...")
    app.run_polling()


if __name__ == '__main__':
    main()
# --- End of modified file: telegram_bot/bot.py ---