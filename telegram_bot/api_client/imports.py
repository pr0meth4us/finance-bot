import os
import logging
import requests
from .core import ensure_auth

log = logging.getLogger(__name__)


@ensure_auth
def upload_bank_statement(telegram_id, file_bytes, filename, token=None):
    """
    Uploads a bank statement to the backend for parsing.
    The ensure_auth decorator injects the valid JWT token.
    """
    # Fallback to standard local port if env variable is missing
    base_url = os.getenv("WEB_SERVICE_URL", "http://localhost:5001/api")
    url = f"{base_url}/imports/upload"
    headers = {'Authorization': f'Bearer {token}'}

    # requests automatically sets the correct multipart/form-data boundary
    # and Content-Type when passing data via the 'files' parameter.
    files = {'file': (filename, file_bytes)}

    try:
        response = requests.post(url, headers=headers, files=files, timeout=60)

        # Allow ensure_auth to catch 401s and trigger a re-login if necessary
        if response.status_code == 401:
            response.raise_for_status()

        return response.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API upload_bank_statement failed: {e}")
        # Attempt to extract a clean error message from the backend if available
        if 'response' in locals() and response is not None:
            try:
                return response.json()
            except ValueError:
                pass
        return {"error": "Failed to connect to the server or process the file."}