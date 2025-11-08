# --- Start of modified file: telegram_bot/bot.py ---
import os
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler
)
from dotenv import load_dotenv

from handlers import (
    start, quick_check, cancel,
    tx_conversation_handler,
    iou_conversation_handler,
    repay_lump_conversation_handler,
    forgot_conversation_handler,
    reminder_conversation_handler,
    report_conversation_handler,
    edit_tx_conversation_handler,
    habits_conversation_handler,
    search_conversation_handler,
    history_menu, manage_transaction, delete_transaction_prompt,
    delete_transaction_confirm,
    iou_menu, iou_view, iou_person_detail, iou_detail, debt_analysis,
    iou_view_settled, iou_person_detail_settled, iou_manage_list,
    iou_manage_menu, iou_cancel_prompt, iou_cancel_confirm,
    iou_edit_conversation_handler,
    get_current_rate
)
from handlers.command_handler import unified_message_conversation_handler
# New imports for settings and onboarding
from handlers.onboarding import onboarding_conversation_handler
from handlers.settings import settings_conversation_handler

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

    # 2. Add button-based conversation handlers
    app.add_handler(tx_conversation_handler)
    app.add_handler(iou_conversation_handler)
    app.add_handler(repay_lump_conversation_handler)
    app.add_handler(forgot_conversation_handler)
    app.add_handler(reminder_conversation_handler)
    app.add_handler(report_conversation_handler)
    app.add_handler(edit_tx_conversation_handler)
    app.add_handler(habits_conversation_handler)
    app.add_handler(search_conversation_handler)
    app.add_handler(iou_edit_conversation_handler)

    # 3. NEW: Add Onboarding and Settings handlers
    app.add_handler(onboarding_conversation_handler)
    app.add_handler(settings_conversation_handler)

    # 4. The unified message handler (for !commands and unknown text)
    app.add_handler(unified_message_conversation_handler)

    # 5. Standalone callback handlers for specific button presses
    app.add_handler(CallbackQueryHandler(start, pattern='^start$'))
    app.add_handler(
        CallbackQueryHandler(quick_check, pattern='^quick_check$')
    )
    app.add_handler(CallbackQueryHandler(history_menu, pattern='^history$'))
    app.add_handler(
        CallbackQueryHandler(manage_transaction, pattern='^manage_tx_')
    )
    app.add_handler(
        CallbackQueryHandler(delete_transaction_prompt, pattern='^delete_tx_')
    )
    app.add_handler(
        CallbackQueryHandler(delete_transaction_confirm,
                             pattern='^confirm_delete_')
    )
    app.add_handler(
        CallbackQueryHandler(get_current_rate, pattern='^get_live_rate$')
    )

    app.add_handler(CallbackQueryHandler(iou_menu, pattern='^iou_menu$'))
    app.add_handler(CallbackQueryHandler(iou_view, pattern='^iou_view$'))
    app.add_handler(
        CallbackQueryHandler(iou_view_settled, pattern='^iou_view_settled$')
    )
    app.add_handler(
        CallbackQueryHandler(iou_person_detail, pattern='^iou:person:open:')
    )
    app.add_handler(
        CallbackQueryHandler(iou_person_detail_settled,
                             pattern='^iou:person:settled:')
    )
    app.add_handler(CallbackQueryHandler(iou_detail, pattern='^iou:detail:'))
    app.add_handler(
        CallbackQueryHandler(iou_manage_list, pattern='^iou:manage:list:')
    )
    app.add_handler(
        CallbackQueryHandler(iou_manage_menu, pattern='^iou:manage:detail:')
    )
    app.add_handler(
        CallbackQueryHandler(iou_cancel_prompt, pattern='^iou:cancel:prompt:')
    )
    app.add_handler(
        CallbackQueryHandler(iou_cancel_confirm,
                             pattern='^iou:cancel:confirm:')
    )
    app.add_handler(
        CallbackQueryHandler(debt_analysis, pattern='^debt_analysis$')
    )

    print("🚀 Bot is running...")
    app.run_polling()


if __name__ == '__main__':
    main()
# --- End of modified file ---