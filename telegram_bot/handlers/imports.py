import os
import logging
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from decorators import authenticate_user
from api_client.imports import upload_bank_statement

log = logging.getLogger(__name__)

# Fallback URL if not set in the environment variables
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://savvify-web.vercel.app")


@authenticate_user
async def prompt_import_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Triggered when a user clicks the "Import Statement" button in a menu.
    Instructs the user on how to proceed.
    """
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "📥 <b>Import Bank Statement</b>\n\n"
        "To import your transactions, simply upload your bank statement directly into this chat as a document.\n\n"
        "<b>Supported Banks:</b>\n"
        "• ABA Bank\n"
        "• ACLEDA Bank\n\n"
        "<b>Supported Formats:</b>\n"
        "• <code>.csv</code>\n"
        "• <code>.xlsx</code>",
        parse_mode='HTML'
    )


@authenticate_user
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Intercepts document uploads, validates the extension, downloads the file
    into memory, and streams it to the Flask backend for parsing.
    """
    message = update.message
    document = message.document

    # 1. Validate File Extension
    if not document.file_name.lower().endswith(('.csv', '.xlsx')):
        await message.reply_text(
            "⚠️ Please upload a valid <code>.csv</code> or <code>.xlsx</code> bank statement.",
            parse_mode='HTML'
        )
        return

    status_msg = await message.reply_text("⏳ Analyzing bank statement...", parse_mode='HTML')

    try:
        # 2. Download File into Memory
        file = await context.bot.get_file(document.file_id)
        file_byte_array = await file.download_as_bytearray()

        # USE JWT from context, exactly like all other API endpoints do
        jwt_token = context.user_data.get('jwt')

        # 3. Send to Flask Backend
        result = upload_bank_statement(bytes(file_byte_array), document.file_name, user_id=jwt_token)

        # Handle backend errors (e.g., UnsupportedBankError)
        if 'error' in result:
            safe_error = html.escape(result['error'])
            await status_msg.edit_text(f"❌ <b>Error:</b> {safe_error}", parse_mode='HTML')
            return

        # 4. Generate Web App UI Response
        session_id = result.get('session_id')
        count = result.get('transaction_count', 0)
        safe_filename = html.escape(document.file_name)

        # Construct the deep link to the specific Next.js import review page
        web_app_url = f"{FRONTEND_URL.rstrip('/')}/dashboard/import/{session_id}"

        keyboard = [
            [InlineKeyboardButton("📝 Review & Import", web_app=WebAppInfo(url=web_app_url))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await status_msg.edit_text(
            f"✅ <b>Statement Parsed Successfully!</b>\n\n"
            f"Found <b>{count}</b> transactions in <code>{safe_filename}</code>.\n\n"
            f"Click the button below to review your transactions and remove any duplicates before importing.",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    except Exception as e:
        log.error(f"Error handling document upload for user {update.effective_user.id}: {e}")
        await status_msg.edit_text(
            "❌ Failed to process the statement. Ensure it is a valid ABA or ACLEDA file.",
            parse_mode='HTML'
        )