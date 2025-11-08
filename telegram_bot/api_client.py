# --- Start of refactored file: telegram_bot/api_client.py ---
import os
import requests
from dotenv import load_dotenv
import urllib.parse

load_dotenv()
BASE_URL = os.getenv("WEB_SERVICE_URL")

# --- NEW AUTH FUNCTION ---
def find_or_create_user(telegram_id):
    """
    Checks the user's status and performs initial creation/onboarding check on the backend.
    """
    try:
        data = {"telegram_user_id": str(telegram_id)}
        res = requests.post(f"{BASE_URL}/auth/find_or_create", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error finding or creating user: {e}")
        try:
            return e.response.json()
        except:
            return {'error': 'A network error occurred.'}

# --- NEW ADMIN CHECK ---
def check_admin_status(telegram_id):
    """
    Checks if the user has an admin role.
    """
    try:
        data = {"telegram_user_id": str(telegram_id)}
        res = requests.post(f"{BASE_URL}/auth/check_admin", json=data, timeout=5)
        res.raise_for_status()
        return res.json().get('is_admin', False)
    except requests.exceptions.RequestException as e:
        print(f"API Error checking admin status: {e}")
        return False

# --- ALL FUNCTIONS ARE MODIFIED TO ACCEPT AND SEND user_id ---

def get_detailed_summary(user_id):
    try:
        data = {"telegram_user_id": str(user_id)}
        res = requests.get(f"{BASE_URL}/summary/detailed", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching detailed summary: {e}")
        return None


def add_debt(user_id, data):
    try:
        data["telegram_user_id"] = str(user_id) # Inject user_id
        res = requests.post(f"{BASE_URL}/debts/", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error adding debt: {e}")
        return None


def add_reminder(user_id, data):
    try:
        data["telegram_user_id"] = str(user_id) # Inject user_id
        res = requests.post(f"{BASE_URL}/reminders/", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error adding reminder: {e}")
        return None


def get_open_debts(user_id):
    try:
        data = {"telegram_user_id": str(user_id)}
        res = requests.get(f"{BASE_URL}/debts/", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debts: {e}")
        return []


def get_settled_debts_grouped(user_id):
    try:
        data = {"telegram_user_id": str(user_id)}
        res = requests.get(f"{BASE_URL}/debts/list/settled", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching settled debts: {e}")
        return []


def get_debts_by_person_and_currency(user_id, person_name, currency):
    try:
        encoded_name = urllib.parse.quote(person_name)
        data = {"telegram_user_id": str(user_id)}
        # NOTE: GET requests typically use query params for data, but since our middleware
        # requires a JSON body for auth, we will send data in the body for consistency.
        # This is a common pattern for API-heavy bot clients.
        res = requests.get(f"{BASE_URL}/debts/person/{encoded_name}/{currency}", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debts for {person_name} ({currency}): {e}")
        return []


def get_all_debts_by_person(user_id, person_name):
    """Fetches all open debts for a person, regardless of currency."""
    try:
        encoded_name = urllib.parse.quote(person_name)
        data = {"telegram_user_id": str(user_id)}
        res = requests.get(f"{BASE_URL}/debts/person/{encoded_name}/all", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching all debts for {person_name}: {e}")
        return []


def get_all_settled_debts_by_person(user_id, person_name):
    """Fetches all settled debts for a person, regardless of currency."""
    try:
        encoded_name = urllib.parse.quote(person_name)
        data = {"telegram_user_id": str(user_id)}
        res = requests.get(f"{BASE_URL}/debts/person/{encoded_name}/all/settled", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching all settled debts for {person_name}: {e}")
        return []


def get_debt_details(user_id, debt_id):
    try:
        data = {"telegram_user_id": str(user_id)}
        res = requests.get(f"{BASE_URL}/debts/{debt_id}", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debt details: {e}")
        return None


def cancel_debt(user_id, debt_id):
    """Sends a POST request to cancel a debt and reverse its transaction."""
    try:
        data = {"telegram_user_id": str(user_id)}
        res = requests.post(f"{BASE_URL}/debts/{debt_id}/cancel", json=data, timeout=15)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error canceling debt: {e}")
        try:
            return e.response.json()
        except:
            return {'error': 'A network error occurred.'}


def update_debt(user_id, debt_id, data):
    """Sends a PUT request to update a debt's person or purpose."""
    try:
        data["telegram_user_id"] = str(user_id) # Inject user_id
        res = requests.put(f"{BASE_URL}/debts/{debt_id}", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error updating debt: {e}")
        try:
            return e.response.json()
        except:
            return {'error': 'A network error occurred.'}


def record_lump_sum_repayment(user_id, person_name, currency, amount, debt_type, timestamp=None):
    """Records a lump-sum repayment."""
    try:
        encoded_currency = urllib.parse.quote(currency)
        url = f"{BASE_URL}/debts/person/{encoded_currency}/repay"
        payload = {
            'telegram_user_id': str(user_id), # Inject user_id
            'amount': amount,
            'type': debt_type,
            'person': person_name
        }
        if timestamp:
            payload['timestamp'] = timestamp

        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error recording lump-sum repayment: {e}")
        try:
            return e.response.json()
        except:
            return {'error': 'A network error occurred.'}


def update_exchange_rate(user_id, rate):
    try:
        data = {'rate': rate, 'telegram_user_id': str(user_id)} # Inject user_id
        res = requests.post(f"{BASE_URL}/settings/rate", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error updating rate: {e}")
        return None


def get_exchange_rate(user_id):
    """Fetches the currently stored KHR to USD exchange rate for the user."""
    try:
        data = {"telegram_user_id": str(user_id)}
        res = requests.get(f"{BASE_URL}/settings/rate", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching rate: {e}")
        return None


def add_transaction(user_id, data):
    try:
        data["telegram_user_id"] = str(user_id) # Inject user_id
        res = requests.post(f"{BASE_URL}/transactions/", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error adding transaction: {e}")
        return None


def get_recent_transactions(user_id):
    try:
        data = {"telegram_user_id": str(user_id)}
        res = requests.get(f"{BASE_URL}/transactions/recent", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching recent transactions: {e}")
        return []


def get_transaction_details(user_id, tx_id):
    try:
        data = {"telegram_user_id": str(user_id)}
        res = requests.get(f"{BASE_URL}/transactions/{tx_id}", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching transaction details: {e}")
        return None


def update_transaction(user_id, tx_id, data):
    """Sends a PUT request to update a transaction."""
    try:
        data["telegram_user_id"] = str(user_id) # Inject user_id
        res = requests.put(f"{BASE_URL}/transactions/{tx_id}", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error updating transaction: {e}")
        return None


def delete_transaction(user_id, tx_id):
    try:
        data = {"telegram_user_id": str(user_id)}
        res = requests.delete(f"{BASE_URL}/transactions/{tx_id}", json=data, timeout=10)
        res.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"API Error deleting transaction: {e}")
        return False


def get_detailed_report(user_id, start_date=None, end_date=None):
    """Fetches detailed report data (income, expense, net) from the API."""
    try:
        params = {"telegram_user_id": str(user_id)}
        if start_date and end_date:
            params['start_date'] = start_date.isoformat()
            params['end_date'] = end_date.isoformat()

        # NOTE: Using POST here to send JSON body containing user_id for auth
        res = requests.post(f"{BASE_URL}/analytics/report/detailed", json=params, timeout=15)
        if res.status_code == 200:
            return res.json()
        return None
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching detailed report: {e}")
        return None


def get_spending_habits(user_id, start_date, end_date):
    """Fetches spending habits analysis from the API."""
    try:
        data = {
            'telegram_user_id': str(user_id),
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
        res = requests.post(f"{BASE_URL}/analytics/habits", json=data, timeout=20)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching spending habits: {e}")
        return None


def get_debt_analysis(user_id):
    """Fetches debt analysis data from the API."""
    try:
        data = {"telegram_user_id": str(user_id)}
        res = requests.get(f"{BASE_URL}/debts/analysis", json=data, timeout=15)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debt analysis: {e}")
        return None


def search_transactions_for_management(user_id, params):
    """Sends a POST request to get a list of transactions for editing."""
    try:
        params["telegram_user_id"] = str(user_id) # Inject user_id
        res = requests.post(f"{BASE_URL}/transactions/search", json=params, timeout=20)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error searching transactions for management: {e}")
        return []


def sum_transactions_for_analytics(user_id, params):
    """Sends a POST request to get a sum of transactions for analytics."""
    try:
        params["telegram_user_id"] = str(user_id) # Inject user_id
        res = requests.post(f"{BASE_URL}/analytics/search", json=params, timeout=20)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error summing transactions: {e}")
        return None

# --- End of refactored file: telegram_bot/api_client.py ---