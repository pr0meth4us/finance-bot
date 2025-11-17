import logging
import requests
from flask import current_app
from cachetools import cached, TTLCache

log = logging.getLogger(__name__)


# Cache the API response for 1 hour
@cached(cache=TTLCache(maxsize=1, ttl=3600))
def get_live_usd_to_khr_rate():
    """
    Fetches the live USD to KHR exchange rate from the API.
    Defaults to 4100.0 on failure.
    """
    api_key = current_app.config.get('EXCHANGERATE_API_KEY')
    if not api_key:
        log.warning("EXCHANGERATE_API_KEY not set. Using default rate of 4100.")
        return 4100.0

    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get('result') == 'success':
            rate = data.get('conversion_rates', {}).get('KHR')
            if rate:
                log.info(f"Live rate fetched: 1 USD = {rate} KHR")
                return float(rate)

    except requests.exceptions.RequestException as e:
        log.error(f"Could not fetch exchange rate: {e}")

    log.warning("Using default rate of 4100 due to API failure.")
    return 4100.0