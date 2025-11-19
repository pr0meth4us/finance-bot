# telegram_bot/utils/bifrost.py

import hashlib
import hmac
import time
import json
import os
import logging

log = logging.getLogger(__name__)


def generate_telegram_hash(user_data: dict, bot_token: str) -> str:
    """
    Generates the HMAC-SHA256 hash for Telegram login data,
    mimicking the browser-based Telegram Login Widget.

    Bifrost requires this hash to verify the data originates from
    a trusted source (us) that possesses the bot_token.
    """
    if not bot_token:
        log.error("Cannot generate hash: Missing Bot Token")
        return ""

    # 1. Filter out None values and the hash itself if present
    data_check_arr = []
    for key, value in sorted(user_data.items()):
        if value is None or key == 'hash':
            continue
        data_check_arr.append(f"{key}={value}")

    # 2. Construct data-check-string (alphabetical order, newline separated)
    data_check_string = '\n'.join(data_check_arr)

    # 3. Calculate Secret Key (SHA256 of the bot token)
    secret_key = hashlib.sha256(bot_token.encode('utf-8')).digest()

    # 4. Calculate HMAC-SHA256 signature
    signature = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return signature


def prepare_bifrost_payload(user, bot_token):
    """
    Constructs the full payload required by Bifrost's /telegram-login endpoint.
    Includes the critical 'hash' field for verification.
    """
    now = int(time.time())

    # Structure matches what Telegram Widget sends
    tg_data = {
        "id": user.id,
        "first_name": user.first_name,
        "username": user.username,
        "auth_date": now
    }

    if user.last_name:
        tg_data["last_name"] = user.last_name

    # Note: The Python Telegram Bot User object usually doesn't provide photo_url
    # directly in this context, so we skip it to avoid signing errors.

    # Sign the data
    tg_data['hash'] = generate_telegram_hash(tg_data, bot_token)

    return tg_data