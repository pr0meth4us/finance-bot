import requests
import time
import logging
from requests.auth import HTTPBasicAuth
from utils.bifrost import prepare_bifrost_payload
from .core import (
    BIFROST_URL, BIFROST_CLIENT_ID, BIFROST_CLIENT_SECRET,
    TELEGRAM_TOKEN, DEFAULT_TIMEOUT, BASE_URL,
    _USER_TOKENS, _get_headers, ensure_auth
)

log = logging.getLogger(__name__)

def get_login_code(telegram_id):
    """
    Asks Bifrost to generate a login code for this Telegram ID.
    Uses Basic Auth (Client Credentials) to talk to Bifrost Internal API.
    Includes Retry logic for sleeping services.
    """
    if not BIFROST_URL or not BIFROST_CLIENT_ID or not BIFROST_CLIENT_SECRET:
        log.error("Missing Bifrost config for OTP generation")
        return None

    url = f"{BIFROST_URL}/internal/generate-otp"
    payload = {"telegram_id": str(telegram_id)}

    # Authenticate as the FinanceBot Service
    auth = HTTPBasicAuth(BIFROST_CLIENT_ID, BIFROST_CLIENT_SECRET)

    # Retry logic for cold starts
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.post(url, json=payload, auth=auth, timeout=DEFAULT_TIMEOUT)
            res.raise_for_status()
            return res.json().get('code')
        except requests.exceptions.ReadTimeout:
            log.warning(
                f"Bifrost request timed out (Attempt {attempt + 1}/{max_retries}). The service might be waking up.")
            if attempt < max_retries - 1:
                time.sleep(2)  # Wait a bit before retrying
                continue
            log.error("Failed to generate OTP from Bifrost: Read timed out after retries.")
            return None
        except Exception as e:
            log.error(f"Failed to generate OTP from Bifrost: {e}")
            return None


def login_to_bifrost(user):
    """
    Authenticates the Telegram user with Bifrost to get a JWT.
    (Kept for internal bot operations / legacy flows)
    """
    if not BIFROST_CLIENT_ID or not TELEGRAM_TOKEN:
        log.error("Missing BIFROST_CLIENT_ID or TELEGRAM_TOKEN env vars")
        return None

    url = f"{BIFROST_URL}/auth/api/telegram-login"

    # 1. Prepare Signed Payload
    tg_data = prepare_bifrost_payload(user, TELEGRAM_TOKEN)

    payload = {
        "client_id": BIFROST_CLIENT_ID,
        "telegram_data": tg_data
    }

    try:
        res = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
        res.raise_for_status()
        data = res.json()

        jwt = data.get('jwt')
        if jwt:
            _USER_TOKENS[user.id] = jwt
            log.info(f"Bifrost login successful for user {user.id}")
            return jwt
        else:
            log.error(f"Bifrost login failed: No JWT returned. Resp: {data}")
            return None

    except requests.exceptions.HTTPError as e:
        log.error(f"Bifrost Login Failed ({e.response.status_code}): {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        log.error(f"Bifrost connection error: {e}")
        return None


@ensure_auth
def link_credentials(email, password, user_id):
    """
    Links email/password credentials to the current user (Telegram) account.
    """
    try:
        payload = {
            'email': email,
            'password': password
        }
        res = requests.post(
            f"{BASE_URL}/link-account",
            json=payload,
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error linking account: {e}")
        try:
            return e.response.json()
        except Exception:
            return {'error': 'Connection failed.'}

def link_telegram_via_token(telegram_id, token):
    """
    Flow: Bot -> Finance Backend -> Bifrost.
    Completes the account linking process using a deep link token.
    """
    url = f"{BASE_URL}/link/complete-telegram"
    payload = {
        "telegram_id": str(telegram_id),
        "token": token
    }

    # This call is public/secured by the high-entropy token itself.
    try:
        res = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT)

        if res.status_code == 200:
            return True, res.json().get('message', 'Linked successfully.')

        err_msg = res.json().get('error', 'Unknown error')
        log.error(f"Link Telegram failed: {res.status_code} - {err_msg}")
        return False, err_msg

    except requests.exceptions.RequestException as e:
        log.error(f"API Error linking telegram via token: {e}")
        return False, "Connection failed."

def sync_subscription_status(telegram_id):
    """
    Asks Bifrost for the latest subscription status via Internal API.
    Returns: 'premium_user' | 'user' | 'guest' | None
    """
    if not BIFROST_URL or not BIFROST_CLIENT_ID or not BIFROST_CLIENT_SECRET:
        log.error("Missing Bifrost config for subscription sync")
        return None

    url = f"{BIFROST_URL}/internal/get-role"
    payload = {"telegram_id": str(telegram_id)}

    # Authenticate as the FinanceBot Service
    auth = HTTPBasicAuth(BIFROST_CLIENT_ID, BIFROST_CLIENT_SECRET)

    try:
        res = requests.post(url, json=payload, auth=auth, timeout=DEFAULT_TIMEOUT)

        if res.status_code == 200:
            return res.json().get('role', 'user')

        log.warning(f"Bifrost Sync Failed ({res.status_code}): {res.text}")
        return None

    except requests.exceptions.RequestException as e:
        log.error(f"Failed to sync subscription with Bifrost: {e}")
        return None