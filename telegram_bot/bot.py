# telegram_bot/bot.py

import os
import logging
import asyncio
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram.error import NetworkError
from dotenv import load_dotenv

from handlers import (
    menu, help_command,
    quick_check, cancel,
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
from handlers.auth import login_command  # <--- IMPORTED HERE
from handlers.analytics import download_report_csv
from handlers.iou import download_debt_analysis_csv
from handlers.command_handler import unified_message_conversation_handler
from handlers.onboarding import onboarding_conversation_handler
from handlers.settings import settings_conversation_handler
from utils.i18n import load_translations

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

logger = logging.getLogger("finance-bot")


async def on_error(update: object, context):
    logger.error("--- Unhandled error processing update ---", exc_info=context.error)


async def post_init(app: Application):
    try:
        logger.info("Running post_init: Deleting webhook...")
        await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"post_init error: {e}", exc_info=True)


def main():
    load_translations()

    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.critical("TELEGRAM_TOKEN not found. Bot cannot start.")
        return

    logger.info(f"Starting Bot. API URL: {os.getenv('WEB_SERVICE_URL')}")

    app = Application.builder().token(token).post_init(post_init).build()
    app.add_error_handler(on_error)

    # --- Handlers ---

    # Global Menu & Help
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))

    # Auth Handlers
    app.add_handler(CommandHandler("login", login_command))  # <--- ADDED
    app.add_handler(CommandHandler("web", login_command))  # <--- ADDED (Alias)

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
    app.add_handler(settings_conversation_handler)

    # Onboarding (Handles /start and /reset)
    app.add_handler(onboarding_conversation_handler)

    # Fallback / Universal Input
    app.add_handler(unified_message_conversation_handler)

    # Callbacks
    app.add_handler(CallbackQueryHandler(quick_check, pattern="^quick_check$"))
    app.add_handler(CallbackQueryHandler(history_menu, pattern="^history$"))
    app.add_handler(CallbackQueryHandler(manage_transaction, pattern="^manage_tx_"))
    app.add_handler(CallbackQueryHandler(delete_transaction_prompt, pattern="^delete_tx_"))
    app.add_handler(CallbackQueryHandler(delete_transaction_confirm, pattern="^confirm_delete_"))
    app.add_handler(CallbackQueryHandler(get_current_rate, pattern="^get_live_rate$"))

    # IOU Callbacks
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

    # CSV Exports
    app.add_handler(CallbackQueryHandler(download_report_csv, pattern="^report_csv:"))
    app.add_handler(CallbackQueryHandler(download_debt_analysis_csv, pattern="^debt_analysis_csv$"))

    logger.info("🚀 Bot is polling...")

    while True:
        try:
            app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES, stop_signals=None)
        except NetworkError as e:
            logger.warning(f"⚠️ NetworkError during polling (likely Telegram issue): {e}")
            logger.info("♻️ Retrying polling in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            logger.critical(f"🔥 Critical error in polling loop: {e}", exc_info=True)
            logger.info("♻️ Restarting polling in 10 seconds...")
            time.sleep(10)
        else:
            logger.info("Polling stopped cleanly.")
            break


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot shutting down...")
    except Exception as e:
        logger.critical(f"Bot failed to start: {e}", exc_info=True)