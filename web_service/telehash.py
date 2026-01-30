import hashlib
import hmac
import time
import json
import os
from collections import OrderedDict

# --- CONFIGURATION ---
# Replace this with your actual TELEGRAM_TOKEN from .env
BOT_TOKEN = ":"

# Test User Data
USER_DATA = {
    "id": 123456789,
    "first_name": "TestUser",
    "username": "testuser",
    "auth_date": int(time.time()),  # Current timestamp
    # "photo_url": "", # Optional
    # "last_name": ""  # Optional
}


def generate_hash(data, token):
    """
    Generates the Telegram authentication hash.
    1. Create data-check-string (key=value pairs sorted alphabetically).
    2. Create secret_key = SHA256(bot_token).
    3. Calculate HMAC-SHA256(secret_key, data-check-string).
    """
    # 1. Filter out 'hash' and sort alphabetically by key
    sorted_data = OrderedDict(sorted(data.items()))

    # 2. Construct the data-check-string
    data_check_string = "\n".join([f"{k}={v}" for k, v in sorted_data.items() if v is not None])

    print(f"DEBUG: Data String:\n{data_check_string}\n")

    # 3. Create Secret Key
    secret_key = hashlib.sha256(token.encode()).digest()

    # 4. Generate HMAC
    _hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return _hash


if __name__ == "__main__":
    # Generate valid hash
    valid_hash = generate_hash(USER_DATA, BOT_TOKEN)

    # Add hash to the payload
    USER_DATA['hash'] = valid_hash

    # Construct final payload matching your API expectation
    final_payload = {
        "telegram_data": USER_DATA
    }

    print("-" * 30)
    print("✅ COPY THIS JSON INTO SWAGGER:")
    print("-" * 30)
    print(json.dumps(final_payload, indent=2))
    print("-" * 30)