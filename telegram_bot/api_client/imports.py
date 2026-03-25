import logging
import requests
from .core import ensure_auth, _get_headers, BASE_URL

log = logging.getLogger(__name__)


@ensure_auth
def upload_bank_statement(file_bytes, filename, user_id):
    """
    Uploads a bank statement to the backend for parsing.
    Note: user_id is the JWT string injected from context.user_data['jwt']
    """
    # Defensive strip to prevent 308 Redirects dropping the Authorization header
    url = f"{BASE_URL.rstrip('/')}/imports/upload"

    # _get_headers checks if user_id is a JWT string and uses it directly
    headers = _get_headers(user_id)

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