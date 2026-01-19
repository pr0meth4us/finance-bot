import os
import requests
import logging
import time
from dotenv import load_dotenv
from utils.bifrost import prepare_bifrost_payload
import urllib.parse
from requests.auth import HTTPBasicAuth

load_dotenv()
log = logging.getLogger(__name__)

BASE_URL = os.getenv("WEB_SERVICE_URL")
BIFROST_URL = os.getenv("BIFROST_URL", "http://bifrost:5000")
BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID")
BIFROST_CLIENT_SECRET = os.getenv("BIFROST_CLIENT_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Increased timeout to handle PaaS "cold starts" (sleeping instances)
DEFAULT_TIMEOUT = 60

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


# --- NEW AUTH METHOD ---
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


# -----------------------


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


def sync_session(jwt_token):
    """
    Flow A: Session Sync.
    Sends the Bifrost JWT to the Finance Service to validate and ensure a local profile exists.
    """
    url = f"{BASE_URL}/auth/sync-session"
    headers = {"Authorization": f"Bearer {jwt_token}"}

    try:
        res = requests.post(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"Failed to sync session with Finance Backend: {e}")
        return None


def ensure_auth(func):
    """
    Internal decorator for api_client functions to retry requests
    if the token is expired (401).
    """

    def wrapper(*args, **kwargs):
        # Note: logic relies on finding user_id to pop token from cache.
        # If args passed is raw JWT, popping from cache won't help, but
        # the outer auth decorator in decorators.py handles re-login anyway.
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


# --- API METHODS ---

@ensure_auth
def get_my_profile(user_id):
    try:
        res = requests.get(f"{BASE_URL}/users/me", headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching profile: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                return e.response.json()
            except:
                pass
        return None


@ensure_auth
def get_detailed_summary(user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/summary/detailed",
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching detailed summary: {e}")
        return None


@ensure_auth
def add_debt(data, user_id):
    try:
        res = requests.post(f"{BASE_URL}/debts/", json=data, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT)
        if res.status_code == 403:
            raise PremiumFeatureException("Premium required")
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error adding debt: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
            raise PremiumFeatureException("Premium required")
        return None


@ensure_auth
def add_reminder(data, user_id):
    try:
        res = requests.post(f"{BASE_URL}/reminders/", json=data, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error adding reminder: {e}")
        return None


@ensure_auth
def get_open_debts(user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/debts/", headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )
        if res.status_code == 403:
            raise PremiumFeatureException("Premium required")
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching debts: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
            raise PremiumFeatureException("Premium required")
        return []


@ensure_auth
def get_open_debts_export(user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/debts/export/open",
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        if res.status_code == 403:
            raise PremiumFeatureException("Premium required")
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching debts for export: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
            raise PremiumFeatureException("Premium required")
        return []


@ensure_auth
def get_settled_debts_grouped(user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/debts/list/settled",
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        if res.status_code == 403:
            raise PremiumFeatureException("Premium required")
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching settled debts: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
            raise PremiumFeatureException("Premium required")
        return []


@ensure_auth
def get_debts_by_person_and_currency(person_name, currency, user_id):
    try:
        encoded_name = urllib.parse.quote(person_name)
        res = requests.get(
            f"{BASE_URL}/debts/person/{encoded_name}/{currency}",
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(
            f"API Error fetching debts for {person_name} ({currency}): {e}"
        )
        return []


@ensure_auth
def get_all_debts_by_person(person_name, user_id):
    try:
        encoded_name = urllib.parse.quote(person_name)
        res = requests.get(
            f"{BASE_URL}/debts/person/{encoded_name}/all",
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching all debts for {person_name}: {e}")
        return []


@ensure_auth
def get_all_settled_debts_by_person(person_name, user_id):
    try:
        encoded_name = urllib.parse.quote(person_name)
        res = requests.get(
            f"{BASE_URL}/debts/person/{encoded_name}/all/settled",
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(
            f"API Error fetching all settled debts for {person_name}: {e}"
        )
        return []


@ensure_auth
def get_debt_details(debt_id, user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/debts/{debt_id}",
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching debt details: {e}")
        return None


@ensure_auth
def cancel_debt(debt_id, user_id):
    try:
        res = requests.post(
            f"{BASE_URL}/debts/{debt_id}/cancel",
            json={},  # Body is empty now, user_id in header
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error canceling debt: {e}")
        try:
            return e.response.json()
        except Exception:
            return {'error': 'A network error occurred.'}


@ensure_auth
def update_debt(debt_id, data, user_id):
    try:
        res = requests.put(
            f"{BASE_URL}/debts/{debt_id}", json=data, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error updating debt: {e}")
        try:
            return e.response.json()
        except Exception:
            return {'error': 'A network error occurred.'}


@ensure_auth
def record_lump_sum_repayment(
        person_name, currency, amount, debt_type, user_id, timestamp=None
):
    try:
        encoded_currency = urllib.parse.quote(currency)
        url = f"{BASE_URL}/debts/person/{encoded_currency}/repay"
        payload = {
            'amount': amount,
            'type': debt_type,
            'person': person_name,
            # user_id handled by header
        }
        if timestamp:
            payload['timestamp'] = timestamp

        res = requests.post(url, json=payload, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error recording lump-sum repayment: {e}")
        try:
            return e.response.json()
        except Exception:
            return {'error': 'A network error occurred.'}


@ensure_auth
def update_exchange_rate(rate, user_id):
    try:
        res = requests.post(
            f"{BASE_URL}/settings/rate",
            json={'rate': rate},  # user_id handled by header
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error updating rate: {e}")
        return None


@ensure_auth
def get_exchange_rate(user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/settings/rate",
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching rate: {e}")
        return None


@ensure_auth
def add_transaction(data, user_id):
    try:
        res = requests.post(
            f"{BASE_URL}/transactions/", json=data, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error adding transaction: {e}")
        return None


@ensure_auth
def get_recent_transactions(user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/transactions/recent",
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching recent transactions: {e}")
        return []


@ensure_auth
def get_transaction_details(tx_id, user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/transactions/{tx_id}",
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching transaction details: {e}")
        return None


@ensure_auth
def update_transaction(tx_id, data, user_id):
    try:
        res = requests.put(
            f"{BASE_URL}/transactions/{tx_id}", json=data, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error updating transaction: {e}")
        return None


@ensure_auth
def delete_transaction(tx_id, user_id):
    try:
        res = requests.delete(
            f"{BASE_URL}/transactions/{tx_id}",
            json={},  # Body empty, user_id in header
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        log.error(f"API Error deleting transaction: {e}")
        return False


@ensure_auth
def get_detailed_report(user_id, start_date=None, end_date=None):
    try:
        params = {}
        if start_date and end_date:
            params['start_date'] = start_date.isoformat()
            params['end_date'] = end_date.isoformat()

        res = requests.get(
            f"{BASE_URL}/analytics/report/detailed",
            params=params,
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        if res.status_code == 403:
            raise PremiumFeatureException("Premium required")

        if res.status_code == 200:
            return res.json()

        log.error(f"API Error fetching detailed report (HTTP {res.status_code}): {res.text}")
        return None
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching detailed report: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
            raise PremiumFeatureException("Premium required")
        return None


@ensure_auth
def get_spending_habits(user_id, start_date, end_date):
    try:
        params = {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
        res = requests.get(
            f"{BASE_URL}/analytics/habits", params=params, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )
        if res.status_code == 403:
            raise PremiumFeatureException("Premium required")
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching spending habits: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
            raise PremiumFeatureException("Premium required")
        return None


@ensure_auth
def get_debt_analysis(user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/debts/analysis",
            headers=_get_headers(user_id),
            timeout=DEFAULT_TIMEOUT
        )
        if res.status_code == 403:
            raise PremiumFeatureException("Premium required")

        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching debt analysis: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
            raise PremiumFeatureException("Premium required")
        return None


@ensure_auth
def search_transactions_for_management(params, user_id):
    try:
        res = requests.post(
            f"{BASE_URL}/transactions/search", json=params, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )

        if res.status_code == 403:
            raise PremiumFeatureException("Premium required")

        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error searching transactions for management: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
            raise PremiumFeatureException("Premium required")
        return []


@ensure_auth
def sum_transactions_for_analytics(params, user_id):
    try:
        res = requests.post(
            f"{BASE_URL}/analytics/search", json=params, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )
        if res.status_code == 403:
            raise PremiumFeatureException("Premium required")

        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error summing transactions: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
            raise PremiumFeatureException("Premium required")
        return None


@ensure_auth
def get_user_settings(user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/settings/", headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching settings: {e}")
        return None


@ensure_auth
def update_initial_balance(user_id, currency, amount):
    try:
        payload = {
            'currency': currency,
            'amount': amount
        }
        res = requests.post(
            f"{BASE_URL}/settings/balance", json=payload, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error updating initial balance: {e}")
        return None


@ensure_auth
def update_user_mode(user_id, mode, language=None, name_en=None, name_km=None, primary_currency=None):
    try:
        payload = {
            'mode': mode,
            'name_en': name_en
        }
        if language:
            payload['language'] = language
        if name_km:
            payload['name_km'] = name_km
        if primary_currency:
            payload['primary_currency'] = primary_currency

        res = requests.post(
            f"{BASE_URL}/settings/mode", json=payload, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error updating user mode: {e}")
        return None


@ensure_auth
def complete_onboarding(user_id):
    try:
        res = requests.post(
            f"{BASE_URL}/settings/complete_onboarding", json={}, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error completing onboarding: {e}")
        return None


@ensure_auth
def add_category(user_id, cat_type, cat_name):
    try:
        payload = {
            'type': cat_type,
            'name': cat_name
        }
        res = requests.post(
            f"{BASE_URL}/settings/category", json=payload, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )
        if res.status_code == 403:
            raise PremiumFeatureException("Premium required")

        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error adding category: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
            raise PremiumFeatureException("Premium required")
        return None


@ensure_auth
def remove_category(user_id, cat_type, cat_name):
    try:
        payload = {
            'type': cat_type,
            'name': cat_name
        }
        res = requests.delete(
            f"{BASE_URL}/settings/category", json=payload, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )
        if res.status_code == 403:
            raise PremiumFeatureException("Premium required")

        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error removing category: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
            raise PremiumFeatureException("Premium required")
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
            f"{BASE_URL}/auth/link-account",
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