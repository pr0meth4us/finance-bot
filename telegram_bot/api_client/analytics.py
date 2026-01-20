import requests
import logging
from .core import BASE_URL, DEFAULT_TIMEOUT, PremiumFeatureException, _get_headers, ensure_auth

log = logging.getLogger(__name__)

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