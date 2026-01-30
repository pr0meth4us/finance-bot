# telegram_bot/utils/bifrost.py

import hashlib
import hmac
import time
from collections import OrderedDict

def prepare_bifrost_payload(user, bot_token):
    """
    Creates a valid Telegram Login payload signed with the bot token.
    Matches Bifrost's server-side verification logic.
    """
    # 1. Construct standard Telegram Auth Object
    # All values must be converted to strings to ensure consistent hashing
    user_data = {
        'auth_date': str(int(time.time())),
        'first_name': user.first_name,
        'id': str(user.id),
        'username': user.username or "",
    }

    # Optional fields - Only include if they exist
    if user.last_name:
        user_data['last_name'] = user.last_name
    if user.language_code:
        user_data['language_code'] = user.language_code

    # NOTE: photo_url is NOT available in Bot API User objects.
    # We omit it; Bifrost does not require it for authentication.

    # 2. Create data-check-string (key=value\n...)
    # Bifrost expects keys sorted alphabetically
    sorted_items = sorted(user_data.items())

    # Filter out None values just in case
    data_check_string = "\n".join([f"{k}={v}" for k, v in sorted_items if v is not None])

    # 3. Create Secret Key = SHA256(bot_token)
    secret_key = hashlib.sha256(bot_token.encode()).digest()

    # 4. Calculate HMAC-SHA256
    _hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    # 5. Add hash to payload (Bifrost expects 'hash' in the payload)
    user_data['hash'] = _hash

    return user_data