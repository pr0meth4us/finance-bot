import requests
from flask import current_app
from cachetools import cached, TTLCache

# Cache the API response for 1 hour (3600 seconds) to avoid excessive API calls
@cached(cache=TTLCache(maxsize=1, ttl=3600))
def get_live_usd_to_khr_rate():
    """
    Fetches the live USD to KHR exchange rate from the API.
    The result is cached for 1 hour.
    """
    api_key = current_app.config.get('EXCHANGERATE_API_KEY')
    if not api_key:
        print("⚠️ EXCHANGERATE_API_KEY not set. Using default rate of 4100.")
        return 4100.0

    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get('result') == 'success':
            rate = data.get('conversion_rates', {}).get('KHR')
            if rate:
                print(f"✅ Live rate fetched: 1 USD = {rate} KHR")
                return float(rate)
    except requests.exceptions.RequestException as e:
        print(f"❌ Could not fetch exchange rate: {e}")

    # Fallback to a default rate if API fails
    print("⚠️ Using default rate of 4100 due to API failure.")
    return 4100.0