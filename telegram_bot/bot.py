# --- telegram_bot/bot.py (FULL) ---
import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
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
# --- NEW IMPORTS ---
from handlers.analytics import download_report_csv
from handlers.iou import download_debt_analysis_csv
# --- END NEW IMPORTS ---
from handlers.command_handler import unified_message_conversation_handler
from handlers.onboarding import onboarding_conversation_handler
from handlers.settings import settings_conversation_handler
from utils.i18n import load_translations

load_dotenv()

# --- MODIFIED: More detailed logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# Set httpx logger to WARNING to reduce noise, unless DEBUG is needed
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

logger = logging.getLogger("finance-bot")
# --- END MODIFICATION ---


async def on_error(update: object, context):
    """
    Logs errors caused by updates.
    This is the most important function for debugging production issues.
    """
    logger.error(
        "--- Unhandled error processing update ---",
        exc_info=context.error
    )

    # Log the update object itself to see what caused the error
    if isinstance(update, Update):
        logger.error(f"Update: {update}")
    else:
        logger.error(f"Update object (type {type(update)}): {update}")

    # Log user data if available, to trace user state
    if context and context.user_data:
        logger.error(f"User Data: {context.user_data}")


# --- NEW: post_init function ---
async def post_init(app: Application):
    """
    Runs after the Application is built, but before polling starts.
    Used to delete any existing webhook to prevent 409 Conflict errors.
    """
    try:
        logger.info("Running post_init: Attempting to delete webhook...")
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("post_init: Webhook deleted successfully.")
    except Exception as e:
        logger.error(f"post_init: Error deleting webhook: {e}", exc_info=True)
# --- END NEW FUNCTION ---


def main():  # <-- MODIFICATION: Changed back to synchronous
    # Load translations into memory on boot
    load_translations()

    # --- DEBUG TRACING ---
    logger.info("--- Starting Bot ---")
    logger.info(f"WEB_SERVICE_URL: {os.getenv('WEB_SERVICE_URL')}")
    logger.info(f"MONGODB_URI (Bot check, not used directly): {os.getenv('MONGODB_URI', 'NOT SET')[:15]}...")
    # --- END DEBUG TRACING ---

    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.critical("❌ TELEGRAM_TOKEN not found. Bot cannot start.")
        return

    # --- MODIFICATION: Added post_init hook ---
    app = Application.builder().token(token).post_init(post_init).build()

    app.add_error_handler(on_error)

    # System commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))

    # Conversations
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
    app.add_handler(onboarding_conversation_handler)
    app.add_handler(settings_conversation_handler)
    app.add_handler(unified_message_conversation_handler)

    # Callback-only handlers
    app.add_handler(CallbackQueryHandler(start, pattern="^start$"))
    app.add_handler(CallbackQueryHandler(quick_check, pattern="^quick_check$"))
    app.add_handler(CallbackQueryHandler(history_menu, pattern="^history$"))
    app.add_handler(CallbackQueryHandler(manage_transaction, pattern="^manage_tx_"))
    app.add_handler(CallbackQueryHandler(delete_transaction_prompt, pattern="^delete_tx_"))
    app.add_handler(CallbackQueryHandler(delete_transaction_confirm, pattern="^confirm_delete_"))
    app.add_handler(CallbackQueryHandler(get_current_rate, pattern="^get_live_rate$"))

    app.add_handler(CallbackQueryHandler(iou_menu, pattern="^iou_menu$"))
    app.add_handler(CallbackQueryHandler(iou_view, pattern="^iou_view$"))
    app.add_handler(CallbackQueryHandler(iou_view_settled, pattern="^iou_view_settled$"))
    app.add_handler(CallbackQueryHandler(iou_person_detail, pattern="^iou:person:open:"))
    app.add_handler(CallbackQueryHandler(iou_person_detail_settled, pattern="^iou:person:settled:"))
    app.add_handler(CallbackQueryHandler(iou_detail, pattern="^iou:detail:"))
    app.add_handler(CallbackQueryHandler(iou_manage_list, pattern="^iou:manage:list:"))
    app.add_handler(CallbackQueryHandler(iou_manage_menu, pattern="^iou:manage:detail:"))
    app.add_handler(CallbackQueryHandler(iou_cancel_prompt, pattern="^iou:cancel:prompt:"))
    app.add_handler(CallbackQueryHandler(iou_cancel_confirm, pattern="^iou:cancel:confirm:"))
    app.add_handler(CallbackQueryHandler(debt_analysis, pattern="^debt_analysis$"))

    # --- NEW CSV EXPORT HANDLERS ---
    app.add_handler(CallbackQueryHandler(download_report_csv, pattern="^report_csv:"))
    app.add_handler(CallbackQueryHandler(download_debt_analysis_csv, pattern="^debt_analysis_csv$"))
    # --- END NEW HANDLERS ---

    logger.info("🚀 Bot is starting polling...")

    # --- MODIFICATION: This is now a blocking, synchronous call ---
    # It will run forever until a stop signal is received.
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
        stop_signals=None,  # Let container orchestrator send SIGTERM
    )


if __name__ == "__main__":
    # --- MODIFICATION: Call the synchronous main() function directly ---
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot shutting down...")
    except Exception as e:
        logger.critical(f"Bot failed to start: {e}", exc_info=True)