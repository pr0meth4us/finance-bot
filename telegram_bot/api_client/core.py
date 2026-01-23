# telegram_bot/api_client/core.py

import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

BASE_URL = os.getenv("WEB_SERVICE_URL")
BIFROST_URL = os.getenv("BIFROST_URL", "http://bifrost:5000")
BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID")
BIFROST_CLIENT_SECRET = os.getenv("BIFROST_CLIENT_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Increased timeout to handle PaaS "cold starts" (sleeping instances)
DEFAULT_TIMEOUT = 60
# Dedicated timeout for Bifrost calls to ensure consistency
BIFROST_TIMEOUT = 60

# In-memory token storage: { user_id: "jwt_token" }
_USER_TOKENS = {}


class PremiumFeatureException(Exception):
    """Raised when the API returns a 403 Forbidden indicating a premium feature."""
    pass


class UpstreamUnavailable(Exception):
    """Raised when the web service or Cloudflare/Koyeb is down (5xx, Timeout)."""
    pass


def _get_headers(user_id_or_token):
    """
    Returns headers with the Bearer token.
    Accepts either a Telegram User ID (int/str) to look up in cache,
    or a raw JWT string directly.
    """
    # 1. Check if the argument is likely a raw JWT (long string)
    if isinstance(user_id_or_token, str) and len(user_id_or_token) > 50:
        return {"Authorization": f"Bearer {user_id_or_token}"}

    # 2. Otherwise, treat as User ID and look up in cache
    token = _USER_TOKENS.get(user_id_or_token)
    if token:
        return {"Authorization": f"Bearer {token}"}

    return {}


def ensure_auth(func):
    """
    Internal decorator for api_client functions to retry requests
    if the token is expired (401).
    """

    def wrapper(*args, **kwargs):
        # Note: logic relies on finding user_id to pop token from cache.
        user_id = kwargs.get('user_id')
        if not user_id and args:
            user_id = args[-1]

        if not user_id:
            return func(*args, **kwargs)

        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                log.warning(f"401 received. Clearing token for identifier: {user_id}")
                _USER_TOKENS.pop(user_id, None)
                # Propagate error so bot knows to re-login
                raise e
            raise e
        except requests.exceptions.RequestException as e:
            log.error(f"Connection error in {func.__name__}: {e}")
            return None

    return wrapper