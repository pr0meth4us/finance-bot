# web_service/app/utils/telegram_helpers.py

import requests

def send_telegram_message(chat_id, text, token, parse_mode='HTML'):
    """A simple function to send a message via the Telegram API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        print(f"Sent scheduled message to {chat_id}.")
    except Exception as e:
        print(f"Failed to send scheduled message to {chat_id}: {e}")


def send_telegram_photo(chat_id, photo_bytes, token, caption=""):
    """Sends a photo from bytes via the Telegram API."""
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    files = {'photo': ('report_chart.png', photo_bytes, 'image/png')}
    data = {'chat_id': chat_id, 'caption': caption}
    try:
        response = requests.post(url, data=data, files=files, timeout=30)
        response.raise_for_status()
        print(f"Sent scheduled photo to {chat_id}.")
    except Exception as e:
        print(f"Failed to send scheduled photo to {chat_id}: {e}")