import requests
import logging
from .core import BASE_URL, DEFAULT_TIMEOUT, PremiumFeatureException, _get_headers, ensure_auth

log = logging.getLogger(__name__)

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