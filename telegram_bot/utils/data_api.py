# --- Start of new file: web_service/app/utils/data_api.py ---
"""
Helper utility for making calls to the MongoDB Atlas Data API.
"""
import requests
import logging
from flask import current_app

log = logging.getLogger(__name__)

def call_data_api(action, payload):
    """
    Constructs and sends a request to the Atlas Data API.

    Args:
        action (str): The Data API action (e.g., "findOne", "insertOne").
        payload (dict): The specific payload for that action (filter, document, etc.).

    Returns:
        (dict, int): A tuple of (response_json, status_code)
    """
    api_url = current_app.config.get("DATA_API_URL")
    api_key = current_app.config.get("DATA_API_KEY")

    if not api_url or not api_key:
        log.error("DATA_API_URL or DATA_API_KEY is not configured.")
        return {"error": "Data API is not configured"}, 500

    # The full URL for the Data API action
    url = f"{api_url}/action/{action}"

    # The standard headers required by the Data API
    headers = {
        'Content-Type': 'application/json',
        'api-key': api_key,
        'Accept': 'application/json'
    }

    # The final data payload, including the cluster/db/collection info
    data = {
        "dataSource": "expTracker",  # Cluster name
        "database": "expTracker",     # DB name
        **payload                   # Merges the action-specific payload
    }

    try:
        log.info(f"Calling Data API: {action}")
        res = requests.post(url, headers=headers, json=data, timeout=10)

        # Check for HTTP-level errors (e.g., 401 Unauthorized, 404 Not Found)
        res.raise_for_status()

        response_json = res.json()

        # Check for Data API-level errors
        if "error" in response_json:
            log.error(f"Data API returned an error: {response_json['error']}")
            return response_json, 500

        log.info(f"Data API call successful: {action}")
        return response_json, res.status_code

    except requests.exceptions.HTTPError as e:
        log.error(f"Data API HTTP Error: {e.response.status_code} {e.response.text}")
        return {"error": "Data API HTTP error", "details": e.response.text}, e.response.status_code
    except requests.exceptions.RequestException as e:
        log.error(f"Data API RequestException: {e}", exc_info=True)
        return {"error": "Data API connection failed", "details": str(e)}, 500
# --- End of new file ---