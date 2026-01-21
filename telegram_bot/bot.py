# telegram_bot/bot.py

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

# Import the Facade
import api_client

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
    get_current_rate,
    upgrade_start, upgrade_confirm
)
from handlers.auth import login_command
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


# --- Deep Link Handler (Clickable URLs) ---
async def deep_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /start link_<token> to connect Web accounts to Telegram.
    This must run BEFORE the Onboarding handler to catch the command.
    """
    args = context.args
    if not args or not args[0].startswith('link_'):
        # If no link args, pass through to other handlers (handled by Onboarding)
        return

    token = args[0].replace('link_', '')
    await _process_linking(update, token)


# --- Manual Link Handler (Typed Command) ---
async def manual_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /link <token> for users who cannot use deep links.
    """
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /link <token>\nExample: `/link link_abc123`", parse_mode='Markdown')
        return

    token = args[0]
    # Be flexible: allow user to paste full 'link_xyz' or just 'xyz'
    if token.startswith('link_'):
        token = token.replace('link_', '')

    await _process_linking(update, token)


async def _process_linking(update: Update, token: str):
    """Shared logic for processing the link token."""
    user_id = update.effective_user.id
    await update.message.reply_text("🔗 Processing your account link request...")

    # Attempt to link
    success, msg = api_client.link_telegram_via_token(user_id, token)

    if success:
        await update.message.reply_text(f"✅ Success! {msg}\n\nYou can now use the bot to manage your finances.")
        # Refresh session
        api_client.login_to_bifrost(update.effective_user)
    else:
        await update.message.reply_text(f"❌ Link Failed: {msg}\n\nThe link may have expired or is invalid.")


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

    # 1. Deep Link Handler (Must be registered early)
    app.add_handler(CommandHandler("start", deep_link_handler, filters=None, has_args=True))

    # 2. Manual Link Handler (New)
    app.add_handler(CommandHandler("link", manual_link_handler))

    # Global Menu & Help
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(menu, pattern="^menu$"))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))

    # Auth Handlers
    app.add_handler(CommandHandler("login", login_command))
    app.add_handler(CommandHandler("web", login_command))

    # --- NEW: Upgrade Handler ---
    app.add_handler(CommandHandler("upgrade", upgrade_start))
    app.add_handler(CallbackQueryHandler(upgrade_start, pattern="^upgrade_premium$"))

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

    # Onboarding (Handles standard /start and /reset)
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
    app.add_handler(CommandHandler("upgrade", upgrade_start))
    app.add_handler(CallbackQueryHandler(upgrade_start, pattern="^upgrade_premium$"))  # Legacy entry point

    # NEW: Handle Package Selection (upgrade:1m, upgrade:1y)
    app.add_handler(CallbackQueryHandler(upgrade_confirm, pattern="^upgrade:(1m|1y)$"))

    logger.info("🚀 Bot is polling...")

    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES, stop_signals=None)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot shutting down...")
    except Exception as e:
        logger.critical(f"Bot failed to start: {e}", exc_info=True)