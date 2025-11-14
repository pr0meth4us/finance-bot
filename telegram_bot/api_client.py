# --- telegram_bot/api_client.py (Refactored) ---
import os
import requests
from dotenv import load_dotenv
import urllib.parse
import logging

log = logging.getLogger(__name__)

load_dotenv()
BASE_URL = os.getenv("WEB_SERVICE_URL")
BIFROST_URL = os.getenv("BIFROST_URL")
BIFROST_CLIENT_ID = os.getenv("BIFROST_CLIENT_ID")  # Client ID for the *bot app*


# --- NEW: Custom Exception for Gating ---
class PremiumFeatureException(Exception):
    """Raised when the API returns a 403 Forbidden."""
    pass


def _make_request(method, url, jwt, **kwargs):
    """
    A helper function to make authenticated requests and handle common errors.
    """
    headers = kwargs.pop("headers", {})
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"

    try:
        res = requests.request(method, url, headers=headers, timeout=10, **kwargs)

        # Check for premium feature denial
        if res.status_code == 403:
            raise PremiumFeatureException("This feature requires a premium subscription.")

        # Raise other HTTP errors
        res.raise_for_status()

        # Handle 204 No Content
        if res.status_code == 204:
            return {"success": True}

        return res.json()

    except requests.exceptions.HTTPError as http_err:
        log.error(f"HTTP error occurred: {http_err} - {http_err.response.text}")
        try:
            # Try to return the JSON error from the server
            return http_err.response.json()
        except requests.exceptions.JSONDecodeError:
            return {"error": f"API error ({http_err.response.status_code})"}

    except requests.exceptions.RequestException as e:
        log.error(f"Network error reaching API: {e}", exc_info=True)
        return {"error": "Network error reaching API"}


# --- NEW: Bifrost Authentication Functions ---

def bifrost_telegram_login(telegram_id):
    """
    Logs in a user via their Telegram ID to Bifrost.
    Returns a JWT.
    """
    url = f"{BIFROST_URL}/auth/api/telegram-login"
    payload = {
        "client_id": BIFROST_CLIENT_ID,
        "telegram_id": str(telegram_id)
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        data = res.json()
        if "jwt" in data:
            return data
        else:
            log.error(f"Bifrost login failed: {data.get('error', 'No JWT in response')}")
            return {"error": data.get('error', 'Bifrost login failed')}
    except requests.exceptions.RequestException as e:
        log.error(f"Network error reaching Bifrost: {e}", exc_info=True)
        return {"error": "Network error reaching Auth API"}


def get_my_profile(jwt):
    """
    Fetches the user's own profile (settings, categories, etc.)
    from the web_service's /users/me endpoint.
    This replaces the old find_or_create_user.
    """
    url = f"{BASE_URL}/users/me"
    # _make_request will add the auth header
    return _make_request("get", url, jwt)


# --- REFACTORED: All API functions now use _make_request and JWT ---

def get_detailed_summary(jwt):
    """Fetches detailed summary for the authenticated user."""
    url = f"{BASE_URL}/summary/detailed"
    return _make_request("get", url, jwt)


def add_debt(data, jwt):
    """Adds a new debt for the authenticated user."""
    url = f"{BASE_URL}/debts/"
    return _make_request("post", url, jwt, json=data)


def add_reminder(data, jwt):
    """Adds a new reminder for the authenticated user."""
    url = f"{BASE_URL}/reminders/"
    return _make_request("post", url, jwt, json=data)


def get_open_debts(jwt):
    """Fetches open debts for the authenticated user."""
    url = f"{BASE_URL}/debts/"
    return _make_request("get", url, jwt)


def get_open_debts_export(jwt):
    """Fetches a flat list of all open debts for export."""
    url = f"{BASE_URL}/debts/export/open"
    return _make_request("get", url, jwt)


def get_settled_debts_grouped(jwt):
    """Fetches settled debts for the authenticated user."""
    url = f"{BASE_URL}/debts/list/settled"
    return _make_request("get", url, jwt)


def get_debts_by_person_and_currency(person_name, currency, jwt):
    """Fetches debts by person/currency for the authenticated user."""
    encoded_name = urllib.parse.quote(person_name)
    url = f"{BASE_URL}/debts/person/{encoded_name}/{currency}"
    return _make_request("get", url, jwt)


def get_all_debts_by_person(person_name, jwt):
    """Fetches all open debts for a person, for the authenticated user."""
    encoded_name = urllib.parse.quote(person_name)
    url = f"{BASE_URL}/debts/person/{encoded_name}/all"
    return _make_request("get", url, jwt)


def get_all_settled_debts_by_person(person_name, jwt):
    """Fetches all settled debts for a person, for the authenticated user."""
    encoded_name = urllib.parse.quote(person_name)
    url = f"{BASE_URL}/debts/person/{encoded_name}/all/settled"
    return _make_request("get", url, jwt)


def get_debt_details(debt_id, jwt):
    """Fetches debt details for the authenticated user."""
    url = f"{BASE_URL}/debts/{debt_id}"
    return _make_request("get", url, jwt)


def cancel_debt(debt_id, jwt):
    """Cancels a debt for the authenticated user."""
    url = f"{BASE_URL}/debts/{debt_id}/cancel"
    return _make_request("post", url, jwt)


def update_debt(debt_id, data, jwt):
    """Updates a debt for the authenticated user."""
    url = f"{BASE_URL}/debts/{debt_id}"
    return _make_request("put", url, jwt, json=data)


def record_lump_sum_repayment(
        person_name, currency, amount, debt_type, jwt, timestamp=None
):
    """Records a lump sum repayment for the authenticated user."""
    encoded_currency = urllib.parse.quote(currency)
    url = f"{BASE_URL}/debts/person/{encoded_currency}/repay"
    payload = {
        'amount': amount,
        'type': debt_type,
        'person': person_name
    }
    if timestamp:
        payload['timestamp'] = timestamp
    return _make_request("post", url, jwt, json=payload)


def update_exchange_rate(rate, jwt):
    """Updates the *user's* fixed rate preference."""
    url = f"{BASE_URL}/settings/rate"
    return _make_request("post", url, jwt, json={'rate': rate})


def get_exchange_rate(jwt):
    """Fetches the exchange rate based on user's preference."""
    url = f"{BASE_URL}/settings/rate"
    return _make_request("get", url, jwt)


def add_transaction(data, jwt):
    """Adds a transaction for the authenticated user."""
    url = f"{BASE_URL}/transactions/"
    return _make_request("post", url, jwt, json=data)


def get_recent_transactions(jwt):
    """Fetches recent transactions for the authenticated user."""
    url = f"{BASE_URL}/transactions/recent"
    return _make_request("get", url, jwt)


def get_transaction_details(tx_id, jwt):
    """Fetches transaction details for the authenticated user."""
    url = f"{BASE_URL}/transactions/{tx_id}"
    return _make_request("get", url, jwt)


def update_transaction(tx_id, data, jwt):
    """Updates a transaction for the authenticated user."""
    url = f"{BASE_URL}/transactions/{tx_id}"
    return _make_request("put", url, jwt, json=data)


def delete_transaction(tx_id, jwt):
    """Deletes a transaction for the authenticated user."""
    url = f"{BASE_URL}/transactions/{tx_id}"
    # Delete requests don't typically return JSON, handle 204
    response = _make_request("delete", url, jwt)
    return response.get("success", False)


def get_detailed_report(jwt, start_date=None, end_date=None):
    """Fetches a detailed report for the authenticated user."""
    params = {}
    if start_date and end_date:
        params['start_date'] = start_date.isoformat()
        params['end_date'] = end_date.isoformat()
    url = f"{BASE_URL}/analytics/report/detailed"
    return _make_request("get", url, jwt, params=params)


def get_spending_habits(jwt, start_date, end_date):
    """Fetches spending habits for the authenticated user."""
    params = {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat()
    }
    url = f"{BASE_URL}/analytics/habits"
    return _make_request("get", url, jwt, params=params)


def get_debt_analysis(jwt):
    """Fetches debt analysis for the authenticated user."""
    url = f"{BASE_URL}/debts/analysis"
    return _make_request("get", url, jwt)


def search_transactions_for_management(params, jwt):
    """Searches transactions for the authenticated user."""
    url = f"{BASE_URL}/transactions/search"
    return _make_request("post", url, jwt, json=params)


def sum_transactions_for_analytics(params, jwt):
    """Sums transactions for the authenticated user."""
    url = f"{BASE_URL}/analytics/search"
    return _make_request("post", url, jwt, json=params)


# --- NEW SETTINGS FUNCTIONS (Refactored) ---

def get_user_settings(jwt):
    """Fetches all settings for a user."""
    url = f"{BASE_URL}/settings/"
    return _make_request("get", url, jwt)


def update_initial_balance(jwt, currency, amount):
    """Updates the user's initial balance for one currency."""
    payload = {
        'currency': currency,
        'amount': amount
    }
    url = f"{BASE_URL}/settings/balance"
    return _make_request("post", url, jwt, json=payload)


def update_user_mode(jwt, mode, language=None, name_en=None, name_km=None, primary_currency=None):
    """Sets the user's currency mode and language during onboarding."""
    payload = {
        'mode': mode,
    }
    if language:
        payload['language'] = language
    if name_en:
        payload['name_en'] = name_en
    if name_km:
        payload['name_km'] = name_km
    if primary_currency:
        payload['primary_currency'] = primary_currency

    url = f"{BASE_URL}/settings/mode"
    return _make_request("post", url, jwt, json=payload)


def complete_onboarding(jwt):
    """Marks the user's onboarding as complete."""
    url = f"{BASE_URL}/settings/complete_onboarding"
    return _make_request("post", url, jwt, json={})


def add_category(jwt, cat_type, cat_name):
    """Adds a custom category for a user."""
    payload = {
        'type': cat_type,
        'name': cat_name
    }
    url = f"{BASE_URL}/settings/category"
    return _make_request("post", url, jwt, json=payload)


def remove_category(jwt, cat_type, cat_name):
    """Removes a custom category for a user."""
    payload = {
        'type': cat_type,
        'name': cat_name
    }
    url = f"{BASE_URL}/settings/category"
    return _make_request("delete", url, jwt, json=payload)