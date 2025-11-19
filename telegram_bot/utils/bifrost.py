import hashlib
import hmac
import time
import logging

log = logging.getLogger(__name__)


def generate_telegram_hash(data_dict: dict, bot_token: str) -> str:
    """
    Generates the HMAC-SHA256 hash for Telegram login data.
    This mimics the signature generation of the Telegram Login Widget.

    Bifrost will use this hash to verify the data originated from
    this bot (which holds the token) and hasn't been tampered with.
    """
    # 1. Create the data-check-string
    # Keys must be sorted alphabetically.
    # Format: key=value\nkey=value...
    data_check_arr = []
    for key, value in sorted(data_dict.items()):
        if value is None or key == 'hash':
            continue
        data_check_arr.append(f"{key}={value}")

    data_check_string = '\n'.join(data_check_arr)

    # 2. Calculate the Secret Key
    # The secret key is the SHA256 hash of the bot token (bytes)
    secret_key = hashlib.sha256(bot_token.encode('utf-8')).digest()

    # 3. Calculate the HMAC-SHA256 signature
    signature = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return signature


def prepare_bifrost_payload(user, bot_token: str) -> dict:
    """
    Constructs the full signed payload for Bifrost's /telegram-login endpoint.

    Args:
        user: The telegram.User object.
        bot_token: The Telegram Bot Token.

    Returns:
        dict: A dictionary containing id, first_name, etc., plus the 'hash'.
    """
    if not bot_token:
        raise ValueError("Bot token is missing. Cannot sign payload.")

    now = int(time.time())

    # Construct the data exactly as Telegram sends it
    tg_data = {
        "id": user.id,
        "first_name": user.first_name,
        "username": user.username,
        "auth_date": now
    }

    # Optional fields
    if user.last_name:
        tg_data["last_name"] = user.last_name

    # Note: The python-telegram-bot User object does not always expose photo_url
    # in message updates, so we omit it to ensure signature consistency.

    # Generate signature
    tg_data['hash'] = generate_telegram_hash(tg_data, bot_token)

    return tg_data