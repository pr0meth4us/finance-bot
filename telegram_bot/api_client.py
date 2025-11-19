import os
import requests
import logging
import urllib.parse
from dotenv import load_dotenv
from utils.bifrost import prepare_bifrost_payload

load_dotenv()
log = logging.getLogger(__name__)

# --- Configuration ---
# The URL of the internal Web Service (Business Logic)
WEB_SERVICE_URL = os.getenv("WEB_SERVICE_URL", "http://web_service:8000")

# The URL of the Bifrost Identity Provider
BIFROST_URL = os.getenv("BIFROST_URL", "http://bifrost:5000")

# Credentials for this specific App (Finance Bot) registered in Bifrost
BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


# --- Exceptions ---
class PremiumFeatureException(Exception):
    """Raised when a user tries to access a premium feature without a subscription."""
    pass


class UpstreamUnavailable(Exception):
    """Raised when the web service is unreachable."""
    pass


# --- Token Cache ---
# In-memory storage: { user_id (int): "jwt_token_string" }
_USER_TOKENS = {}


def _get_headers(user_id):
    """Returns headers with the Bearer token for the given user."""
    token = _USER_TOKENS.get(user_id)
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def login_to_bifrost(user):
    """
    Performs a cryptographic handshake with Bifrost.
    1. Signs user data with Bot Token.
    2. Sends to Bifrost.
    3. Receives JWT if signature is valid.
    """
    if not BIFROST_CLIENT_ID or not TELEGRAM_TOKEN:
        log.critical("Missing BIFROST_CLIENT_ID or TELEGRAM_TOKEN env vars")
        return None

    url = f"{BIFROST_URL}/auth/api/telegram-login"

    try:
        # Generate signed payload
        tg_data = prepare_bifrost_payload(user, TELEGRAM_TOKEN)

        payload = {
            "client_id": BIFROST_CLIENT_ID,
            "telegram_data": tg_data
        }

        # Send to Bifrost
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()

        data = res.json()
        jwt = data.get('jwt')

        if jwt:
            _USER_TOKENS[user.id] = jwt
            log.info(f"Bifrost Login Successful for user {user.id}")
            return jwt
        else:
            log.error(f"Bifrost login failed: No JWT returned. Resp: {data}")
            return None

    except requests.exceptions.RequestException as e:
        log.error(f"Bifrost connection error: {e}", exc_info=True)
        return None
    except ValueError as e:
        log.error(f"Signing error: {e}")
        return None


def ensure_auth(func):
    """
    Decorator for API functions.
    Handles 401 (Expired Token) by clearing the local cache so the
    next request triggers a re-login flow in the bot.
    """

    def wrapper(*args, **kwargs):
        # Heuristic to find user_id in args/kwargs
        user_id = kwargs.get('user_id')
        if not user_id and args:
            # Convention: user_id is usually the last positional argument
            user_id = args[-1]

        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            # If token is expired/invalid
            if e.response.status_code == 401:
                if user_id:
                    log.warning(f"401 received for user {user_id}. Clearing cached token.")
                    _USER_TOKENS.pop(user_id, None)
                # Re-raise so the Bot Decorator knows to trigger re-auth
                raise e
            # If forbidden (Premium check)
            elif e.response.status_code == 403:
                raise PremiumFeatureException("Premium subscription required.")
            raise e
        except requests.exceptions.ConnectionError:
            raise UpstreamUnavailable("Web service unreachable.")

    return wrapper


# --- API Methods (Web Service) ---

@ensure_auth
def get_my_profile(user_id):
    """Fetches user profile + role from Web Service."""
    res = requests.get(f"{WEB_SERVICE_URL}/users/me", headers=_get_headers(user_id), timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def get_detailed_summary(jwt_token):
    # Note: This function signature differs slightly as it takes JWT directly in some contexts,
    # or we can adapt it to take user_id. For safety, we use the header helper if possible,
    # but if the caller passes JWT directly (like in decorators), we use that.
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/summary/detailed", headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def add_debt(data, jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.post(f"{WEB_SERVICE_URL}/debts/", json=data, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def add_reminder(data, jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.post(f"{WEB_SERVICE_URL}/reminders/", json=data, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def get_open_debts(jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/debts/", headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def get_open_debts_export(jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/debts/export/open", headers=headers, timeout=15)
    res.raise_for_status()
    return res.json()


@ensure_auth
def get_settled_debts_grouped(jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/debts/list/settled", headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def get_all_debts_by_person(person_name, jwt_token):
    encoded_name = urllib.parse.quote(person_name)
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/debts/person/{encoded_name}/all", headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def get_all_settled_debts_by_person(person_name, jwt_token):
    encoded_name = urllib.parse.quote(person_name)
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/debts/person/{encoded_name}/all/settled", headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def get_debt_details(debt_id, jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/debts/{debt_id}", headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def cancel_debt(debt_id, jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.post(f"{WEB_SERVICE_URL}/debts/{debt_id}/cancel", json={}, headers=headers, timeout=15)
    res.raise_for_status()
    return res.json()


@ensure_auth
def update_debt(debt_id, data, jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.put(f"{WEB_SERVICE_URL}/debts/{debt_id}", json=data, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def record_lump_sum_repayment(person_name, currency, amount, debt_type, jwt_token, timestamp=None):
    encoded_currency = urllib.parse.quote(currency)
    url = f"{WEB_SERVICE_URL}/debts/person/{encoded_currency}/repay"
    payload = {
        'amount': amount,
        'type': debt_type,
        'person': person_name
    }
    if timestamp:
        payload['timestamp'] = timestamp

    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.post(url, json=payload, headers=headers, timeout=15)
    res.raise_for_status()
    return res.json()


@ensure_auth
def update_exchange_rate(rate, jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.post(f"{WEB_SERVICE_URL}/settings/rate", json={'rate': rate}, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def get_exchange_rate(jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/settings/rate", headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def add_transaction(data, jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.post(f"{WEB_SERVICE_URL}/transactions/", json=data, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def get_recent_transactions(jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/transactions/recent", headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def get_transaction_details(tx_id, jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/transactions/{tx_id}", headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def update_transaction(tx_id, data, jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.put(f"{WEB_SERVICE_URL}/transactions/{tx_id}", json=data, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def delete_transaction(tx_id, jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.delete(f"{WEB_SERVICE_URL}/transactions/{tx_id}", headers=headers, timeout=10)
    res.raise_for_status()
    return True


@ensure_auth
def get_detailed_report(jwt_token, start_date, end_date):
    params = {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat()
    }
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/analytics/report/detailed", params=params, headers=headers, timeout=15)
    res.raise_for_status()
    return res.json()


@ensure_auth
def get_spending_habits(jwt_token, start_date, end_date):
    params = {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat()
    }
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/analytics/habits", params=params, headers=headers, timeout=20)
    res.raise_for_status()
    return res.json()


@ensure_auth
def get_debt_analysis(jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/debts/analysis", headers=headers, timeout=15)
    res.raise_for_status()
    return res.json()


@ensure_auth
def search_transactions_for_management(params, jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.post(f"{WEB_SERVICE_URL}/transactions/search", json=params, headers=headers, timeout=20)
    res.raise_for_status()
    return res.json()


@ensure_auth
def sum_transactions_for_analytics(params, jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.post(f"{WEB_SERVICE_URL}/analytics/search", json=params, headers=headers, timeout=20)
    res.raise_for_status()
    return res.json()


@ensure_auth
def get_user_settings(jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.get(f"{WEB_SERVICE_URL}/settings/", headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def update_initial_balance(jwt_token, currency, amount):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    payload = {'currency': currency, 'amount': amount}
    res = requests.post(f"{WEB_SERVICE_URL}/settings/balance", json=payload, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def update_user_mode(jwt_token, mode, language=None, name_en=None, name_km=None, primary_currency=None):
    payload = {'mode': mode}
    if name_en: payload['name_en'] = name_en
    if name_km: payload['name_km'] = name_km
    if language: payload['language'] = language
    if primary_currency: payload['primary_currency'] = primary_currency

    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.post(f"{WEB_SERVICE_URL}/settings/mode", json=payload, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def complete_onboarding(jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.post(f"{WEB_SERVICE_URL}/settings/complete_onboarding", json={}, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def add_category(jwt_token, cat_type, cat_name):
    payload = {'type': cat_type, 'name': cat_name}
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.post(f"{WEB_SERVICE_URL}/settings/category", json=payload, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


@ensure_auth
def remove_category(jwt_token, cat_type, cat_name):
    payload = {'type': cat_type, 'name': cat_name}
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = requests.delete(f"{WEB_SERVICE_URL}/settings/category", json=payload, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()