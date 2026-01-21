import requests
import os
import logging

log = logging.getLogger(__name__)

def notify_user_of_upgrade(telegram_id):
    """
    Sends a congratulatory message to the user via Telegram.
    Called by the Webhook Receiver when a role change is detected.
    """
    bot_token = os.environ.get('TELEGRAM_TOKEN')
    if not bot_token:
        log.error("Cannot notify user: TELEGRAM_TOKEN missing in Web Service.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    message = (
        "🎉 <b>Premium Unlocked!</b>\n\n"
        "Your payment has been confirmed by Bifrost.\n"
        "You now have access to:\n"
        "✨ Unlimited Custom Categories\n"
        "🧠 AI Spending Insights\n"
        "📊 Advanced Reports\n\n"
        "<i>Type /menu to see your new features!</i>"
    )

    payload = {
        "chat_id": telegram_id,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        requests.post(url, json=payload, timeout=5)
        log.info(f"✅ Notification sent to Telegram ID {telegram_id}")
    except Exception as e:
        log.error(f"Failed to send Telegram notification: {e}")