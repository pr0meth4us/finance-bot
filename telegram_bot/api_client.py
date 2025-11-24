# telegram_bot/api_client.py

import os
import logging
import urllib.parse
import requests
import time
from dotenv import load_dotenv
from utils.bifrost import prepare_bifrost_payload

log = logging.getLogger(__name__)

load_dotenv()
BASE_URL = os.getenv("WEB_SERVICE_URL")
# Support both naming conventions from your configs
BIFROST_URL = os.getenv("BIFROST_URL") or os.getenv("BIFROST_BASE_URL")
BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Global session for connection pooling
_session = requests.Session()


class PremiumFeatureException(Exception):
    """Raised when the API returns a 403 Forbidden indicating a premium feature."""
    pass


class UpstreamUnavailable(Exception):
    """Raised when the web service or Cloudflare/Koyeb is down (5xx, Timeout)."""
    pass


def _make_request(method, url, jwt=None, retries=3, **kwargs):
    """
    Helper to make authenticated requests with retries and error handling.
    """
    headers = kwargs.pop("headers", {})
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"

    for attempt in range(retries):
        try:
            res = _session.request(method, url, headers=headers, timeout=10, **kwargs)

            # 1. Handle Premium/Permission errors
            if res.status_code == 403:
                raise PremiumFeatureException("This feature requires a premium subscription.")

            # 2. Handle Server Errors (5xx)
            if res.status_code >= 500:
                log.error(f"Upstream {res.status_code} from {url}. Response: {res.text[:200]}")
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                raise UpstreamUnavailable(f"Service unavailable (Status {res.status_code})")

            # 3. Check other 4xx errors (like 401)
            res.raise_for_status()

            # 4. Success
            if res.status_code == 204:
                return {"success": True}
            return res.json()

        except requests.exceptions.HTTPError as http_err:
            log.error(f"HTTP Client Error: {http_err}")
            # If it's a 401, we return it so the bot can trigger a re-login
            if http_err.response.status_code == 401:
                return {"error": "Unauthorized", "status": 401}

            try:
                return http_err.response.json()
            except Exception:
                return {"error": f"API error ({http_err.response.status_code})"}

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            log.warning(f"Network attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(1)
                continue
            raise UpstreamUnavailable("Connection timed out.")

        except Exception as e:
            log.error(f"Unexpected error calling {url}: {e}", exc_info=True)
            raise UpstreamUnavailable("Network error.")

    raise UpstreamUnavailable("Max retries exceeded.")


# --- Auth ---

def login_to_bifrost(user):
    """
    Authenticates via Telegram ID with Bifrost and returns a JWT.
    """
    if not BIFROST_CLIENT_ID or not TELEGRAM_TOKEN:
        log.error("Missing BIFROST_CLIENT_ID or TELEGRAM_TOKEN")
        return None

    url = f"{BIFROST_URL}/auth/api/telegram-login"

    # Generate signed payload
    tg_data = prepare_bifrost_payload(user, TELEGRAM_TOKEN)

    payload = {
        "client_id": BIFROST_CLIENT_ID,
        "telegram_data": tg_data
    }

    try:
        # Direct request for auth to avoid circular logic
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        data = res.json()

        if "jwt" in data:
            return data["jwt"]
        else:
            log.error(f"Bifrost login failed: {data}")
            return None
    except Exception as e:
        log.error(f"Bifrost Auth Error: {e}")
        return None


# --- User & Settings ---

def get_my_profile(jwt):
    return _make_request("get", f"{BASE_URL}/users/me", jwt)


def get_user_settings(jwt):
    return _make_request("get", f"{BASE_URL}/settings/", jwt)


def update_initial_balance(jwt, currency, amount):
    payload = {'currency': currency, 'amount': amount}
    return _make_request("post", f"{BASE_URL}/settings/balance", jwt, json=payload)


def update_user_mode(jwt, mode, language=None, name_en=None, name_km=None, primary_currency=None):
    payload = {'mode': mode}
    if language: payload['language'] = language
    if name_en: payload['name_en'] = name_en
    if name_km: payload['name_km'] = name_km
    if primary_currency: payload['primary_currency'] = primary_currency
    return _make_request("post", f"{BASE_URL}/settings/mode", jwt, json=payload)


def complete_onboarding(jwt):
    return _make_request("post", f"{BASE_URL}/settings/complete_onboarding", jwt, json={})


def add_category(jwt, cat_type, cat_name):
    payload = {'type': cat_type, 'name': cat_name}
    return _make_request("post", f"{BASE_URL}/settings/category", jwt, json=payload)


def remove_category(jwt, cat_type, cat_name):
    payload = {'type': cat_type, 'name': cat_name}
    return _make_request("delete", f"{BASE_URL}/settings/category", jwt, json=payload)


def update_exchange_rate(rate, jwt):
    return _make_request("post", f"{BASE_URL}/settings/rate", jwt, json={'rate': rate})


def get_exchange_rate(jwt):
    return _make_request("get", f"{BASE_URL}/settings/rate", jwt)


# --- Transactions ---

def add_transaction(data, jwt):
    return _make_request("post", f"{BASE_URL}/transactions/", jwt, json=data)


def get_recent_transactions(jwt):
    return _make_request("get", f"{BASE_URL}/transactions/recent", jwt)


def get_transaction_details(tx_id, jwt):
    return _make_request("get", f"{BASE_URL}/transactions/{tx_id}", jwt)


def update_transaction(tx_id, data, jwt):
    return _make_request("put", f"{BASE_URL}/transactions/{tx_id}", jwt, json=data)


def delete_transaction(tx_id, jwt):
    try:
        res = _make_request("delete", f"{BASE_URL}/transactions/{tx_id}", jwt)
        return True if res and "success" in res else False
    except Exception:
        return False


def search_transactions_for_management(params, jwt):
    return _make_request("post", f"{BASE_URL}/transactions/search", jwt, json=params)


# --- Debts (IOU) ---

def add_debt(data, jwt):
    return _make_request("post", f"{BASE_URL}/debts/", jwt, json=data)


def get_open_debts(jwt):
    return _make_request("get", f"{BASE_URL}/debts/", jwt)


def get_open_debts_export(jwt):
    return _make_request("get", f"{BASE_URL}/debts/export/open", jwt)


def get_settled_debts_grouped(jwt):
    return _make_request("get", f"{BASE_URL}/debts/list/settled", jwt)


def get_debt_details(debt_id, jwt):
    return _make_request("get", f"{BASE_URL}/debts/{debt_id}", jwt)


def get_debts_by_person_and_currency(person_name, currency, jwt):
    encoded = urllib.parse.quote(person_name)
    return _make_request("get", f"{BASE_URL}/debts/person/{encoded}/{currency}", jwt)


def get_all_debts_by_person(person_name, jwt):
    encoded = urllib.parse.quote(person_name)
    return _make_request("get", f"{BASE_URL}/debts/person/{encoded}/all", jwt)


def get_all_settled_debts_by_person(person_name, jwt):
    encoded = urllib.parse.quote(person_name)
    return _make_request("get", f"{BASE_URL}/debts/person/{encoded}/all/settled", jwt)


def update_debt(debt_id, data, jwt):
    return _make_request("put", f"{BASE_URL}/debts/{debt_id}", jwt, json=data)


def cancel_debt(debt_id, jwt):
    return _make_request("post", f"{BASE_URL}/debts/{debt_id}/cancel", jwt)


def record_lump_sum_repayment(person_name, currency, amount, debt_type, jwt, timestamp=None):
    encoded_currency = urllib.parse.quote(currency)
    url = f"{BASE_URL}/debts/person/{encoded_currency}/repay"
    payload = {'amount': amount, 'type': debt_type, 'person': person_name}
    if timestamp:
        payload['timestamp'] = timestamp
    return _make_request("post", url, jwt, json=payload)


def get_debt_analysis(jwt):
    return _make_request("get", f"{BASE_URL}/debts/analysis", jwt)


# --- Analytics & Summary ---

def get_detailed_summary(jwt):
    return _make_request("get", f"{BASE_URL}/summary/detailed", jwt)


def get_detailed_report(jwt, start_date=None, end_date=None):
    params = {}
    if start_date and end_date:
        params['start_date'] = start_date.isoformat()
        params['end_date'] = end_date.isoformat()
    return _make_request("get", f"{BASE_URL}/analytics/report/detailed", jwt, params=params)


def get_spending_habits(jwt, start_date, end_date):
    params = {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat()
    }
    return _make_request("get", f"{BASE_URL}/analytics/habits", jwt, params=params)


def sum_transactions_for_analytics(params, jwt):
    return _make_request("post", f"{BASE_URL}/analytics/search", jwt, json=params)


# --- Reminders ---

def add_reminder(data, jwt):
    return _make_request("post", f"{BASE_URL}/reminders/", jwt, json=data)