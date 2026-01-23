# telegram_bot/api_client/payment.py

import requests
import logging
from requests.auth import HTTPBasicAuth
from .core import (
    BIFROST_URL, BIFROST_CLIENT_ID, BIFROST_CLIENT_SECRET,
    BIFROST_TIMEOUT
)

log = logging.getLogger(__name__)


def create_payment_intent(user_id, amount, duration, target_role, client_ref_id):
    """
    Calls Bifrost to create a secure payment intent.
    Returns the transaction dictionary (containing secure_link) or None.
    """
    if not BIFROST_URL or not BIFROST_CLIENT_ID or not BIFROST_CLIENT_SECRET:
        log.error("Missing Bifrost config for payment intent")
        return None

    # Endpoint added in Bifrost 1.7.0
    url = f"{BIFROST_URL}/internal/payments/secure-intent"

    payload = {
        # account_id is optional; Bifrost will link via Telegram ID during payment
        "amount": float(amount),
        "duration": duration,
        "target_role": target_role,
        "client_ref_id": str(client_ref_id),
        "description": f"Upgrade to {target_role.title()} ({duration})",
        "currency": "USD"
    }

    # Authenticate as the FinanceBot Service
    auth = HTTPBasicAuth(BIFROST_CLIENT_ID, BIFROST_CLIENT_SECRET)

    try:
        res = requests.post(url, json=payload, auth=auth, timeout=BIFROST_TIMEOUT)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        log.error(f"Failed to create payment intent: {e}")
        if hasattr(e, 'response') and e.response is not None:
            log.error(f"Bifrost Response: {e.response.text}")
        return None