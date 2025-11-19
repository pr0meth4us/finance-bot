import os
import requests
import logging
from dotenv import load_dotenv
from utils.bifrost import prepare_bifrost_payload

load_dotenv()
log = logging.getLogger(__name__)

BASE_URL = os.getenv("WEB_SERVICE_URL")
BIFROST_URL = os.getenv("BIFROST_URL", "http://bifrost:5000")  # Default to internal docker name
# The Client ID registered in Bifrost for the Finance Bot
BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# In-memory token storage: { user_id: "jwt_token" }
_USER_TOKENS = {}


def _get_headers(user_id):
    """Returns headers with the Bearer token for the given user."""
    token = _USER_TOKENS.get(user_id)
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def login_to_bifrost(user):
    """
    Authenticates the Telegram user with Bifrost to get a JWT.
    """
    if not BIFROST_CLIENT_ID or not TELEGRAM_TOKEN:
        log.error("Missing BIFROST_CLIENT_ID or TELEGRAM_TOKEN env vars")
        return None

    url = f"{BIFROST_URL}/auth/api/telegram-login"

    # generate signed payload
    tg_data = prepare_bifrost_payload(user, TELEGRAM_TOKEN)

    payload = {
        "client_id": BIFROST_CLIENT_ID,
        "telegram_data": tg_data
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        data = res.json()

        jwt = data.get('jwt')
        if jwt:
            _USER_TOKENS[user.id] = jwt
            return jwt
        else:
            log.error(f"Bifrost login failed: No JWT returned. Resp: {data}")
            return None

    except requests.exceptions.RequestException as e:
        log.error(f"Bifrost connection error: {e}", exc_info=True)
        return None


def ensure_auth(func):
    """
    Internal decorator for api_client functions to retry requests 
    if the token is expired (401).
    """

    def wrapper(*args, **kwargs):
        # Extract user_id. Assumed to be the last positional arg or in kwargs
        user_id = kwargs.get('user_id')
        if not user_id and args:
            # Heuristic: usually user_id is the last arg in our functions
            user_id = args[-1]

        if not user_id:
            # If we can't find a user_id, just run the function (it might fail)
            return func(*args, **kwargs)

        # Try executing
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                log.warning(f"401 received for user {user_id}. Clearing token.")
                _USER_TOKENS.pop(user_id, None)
                # We cannot re-login here easily because we don't have the User object,
                # only the ID. The main bot decorator handles the re-login logic.
                # We simply raise so the bot can handle it.
                raise e
            raise e

    return wrapper


# --- API METHODS ---

@ensure_auth
def get_my_profile(user_id):
    """
    Fetches the user's profile from the Web Service.
    This replaces find_or_create_user. 
    The Web Service will create the profile if it creates a new one.
    """
    try:
        res = requests.get(f"{BASE_URL}/users/me", headers=_get_headers(user_id), timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching profile: {e}")
        # Return the error response if available (e.g. 403 Subscription)
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
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching detailed summary: {e}")
        return None


@ensure_auth
def add_debt(data, user_id):
    try:
        res = requests.post(f"{BASE_URL}/debts/", json=data, headers=_get_headers(user_id), timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error adding debt: {e}")
        return None


@ensure_auth
def add_reminder(data, user_id):
    try:
        res = requests.post(f"{BASE_URL}/reminders/", json=data, headers=_get_headers(user_id), timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error adding reminder: {e}")
        return None


@ensure_auth
def get_open_debts(user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/debts/", headers=_get_headers(user_id), timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching debts: {e}")
        return []


@ensure_auth
def get_open_debts_export(user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/debts/export/open",
            headers=_get_headers(user_id),
            timeout=15
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching debts for export: {e}")
        return []


@ensure_auth
def get_settled_debts_grouped(user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/debts/list/settled",
            headers=_get_headers(user_id),
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching settled debts: {e}")
        return []


@ensure_auth
def get_debts_by_person_and_currency(person_name, currency, user_id):
    try:
        encoded_name = urllib.parse.quote(person_name)
        res = requests.get(
            f"{BASE_URL}/debts/person/{encoded_name}/{currency}",
            headers=_get_headers(user_id),
            timeout=10
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
            timeout=10
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
            timeout=10
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
            timeout=10
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
            timeout=15
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
            f"{BASE_URL}/debts/{debt_id}", json=data, headers=_get_headers(user_id), timeout=10
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

        res = requests.post(url, json=payload, headers=_get_headers(user_id), timeout=15)
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
            timeout=10
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
            timeout=10
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
            f"{BASE_URL}/transactions/", json=data, headers=_get_headers(user_id), timeout=10
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
            timeout=10
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
            timeout=10
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
            f"{BASE_URL}/transactions/{tx_id}", json=data, headers=_get_headers(user_id), timeout=10
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
            timeout=10
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
            timeout=15
        )
        if res.status_code == 200:
            return res.json()

        log.error(f"API Error fetching detailed report (HTTP {res.status_code}): {res.text}")
        return None
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching detailed report: {e}")
        return None


@ensure_auth
def get_spending_habits(user_id, start_date, end_date):
    try:
        params = {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
        res = requests.get(
            f"{BASE_URL}/analytics/habits", params=params, headers=_get_headers(user_id), timeout=20
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching spending habits: {e}")
        return None


@ensure_auth
def get_debt_analysis(user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/debts/analysis",
            headers=_get_headers(user_id),
            timeout=15
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error fetching debt analysis: {e}")
        return None


@ensure_auth
def search_transactions_for_management(params, user_id):
    try:
        res = requests.post(
            f"{BASE_URL}/transactions/search", json=params, headers=_get_headers(user_id), timeout=20
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error searching transactions for management: {e}")
        return []


@ensure_auth
def sum_transactions_for_analytics(params, user_id):
    try:
        res = requests.post(
            f"{BASE_URL}/analytics/search", json=params, headers=_get_headers(user_id), timeout=20
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error summing transactions: {e}")
        return None


@ensure_auth
def get_user_settings(user_id):
    try:
        res = requests.get(
            f"{BASE_URL}/settings/", headers=_get_headers(user_id), timeout=10
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
            f"{BASE_URL}/settings/balance", json=payload, headers=_get_headers(user_id), timeout=10
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
            f"{BASE_URL}/settings/mode", json=payload, headers=_get_headers(user_id), timeout=10
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
            f"{BASE_URL}/settings/complete_onboarding", json={}, headers=_get_headers(user_id), timeout=10
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
            f"{BASE_URL}/settings/category", json=payload, headers=_get_headers(user_id), timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error adding category: {e}")
        return None


@ensure_auth
def remove_category(user_id, cat_type, cat_name):
    try:
        payload = {
            'type': cat_type,
            'name': cat_name
        }
        res = requests.delete(
            f"{BASE_URL}/settings/category", json=payload, headers=_get_headers(user_id), timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API Error removing category: {e}")
        return None