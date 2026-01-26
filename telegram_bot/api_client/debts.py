import requests
import urllib.parse
import logging
from .core import BASE_URL, DEFAULT_TIMEOUT, PremiumFeatureException, _get_headers, ensure_auth

log = logging.getLogger(__name__)

@ensure_auth
def add_debt(data, user_id):
    try:
        res = requests.post(f"{BASE_URL}/debts/", json=data, headers=_get_headers(user_id), timeout=DEFAULT_TIMEOUT)
        if res.status_code == 403:
            raise PremiumFeatureException("Premium required")
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
        log.error(f"API Error recording lump-sum repayment: {e}")
        try:
            return e.response.json()
        except Exception:
            return {'error': 'A network error occurred.'}

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
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
            raise e
        log.error(f"API Error fetching debt analysis: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
            raise PremiumFeatureException("Premium required")
        return None