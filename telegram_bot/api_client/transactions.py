import requests
import logging
from .core import BASE_URL, DEFAULT_TIMEOUT, PremiumFeatureException, _get_headers, ensure_auth

log = logging.getLogger(__name__)

@ensure_auth
def add_transaction(data, user_id):
    try:
        res = requests.post(
            f"{BASE_URL}/transactions/", json=data, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
        log.error(f"API Error deleting transaction: {e}")
        return False


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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
        log.error(f"API Error searching transactions for management: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
            raise PremiumFeatureException("Premium required")
        return []