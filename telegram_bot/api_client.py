# --- Start of modified file: telegram_bot/api_client.py ---
import os
import requests
from dotenv import load_dotenv
import urllib.parse

load_dotenv()
BASE_URL = os.getenv("WEB_SERVICE_URL")


def get_detailed_summary():
    try:
        res = requests.get(f"{BASE_URL}/summary/detailed", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching detailed summary: {e}")
        return None


def add_debt(data):
    try:
        res = requests.post(f"{BASE_URL}/debts/", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error adding debt: {e}")
        return None


def add_reminder(data):
    try:
        res = requests.post(f"{BASE_URL}/reminders/", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error adding reminder: {e}")
        return None


def get_open_debts():
    try:
        res = requests.get(f"{BASE_URL}/debts/", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debts: {e}")
        return []

# --- NEW FUNCTION ---
def get_settled_debts_grouped():
    try:
        res = requests.get(f"{BASE_URL}/debts/list/settled", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching settled debts: {e}")
        return []


def get_debts_by_person_and_currency(person_name, currency):
    try:
        encoded_name = urllib.parse.quote(person_name)
        res = requests.get(f"{BASE_URL}/debts/person/{encoded_name}/{currency}", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debts for {person_name} ({currency}): {e}")
        return []

# --- NEW FUNCTION ---
def get_all_debts_by_person(person_name):
    """Fetches all open debts for a person, regardless of currency."""
    try:
        encoded_name = urllib.parse.quote(person_name)
        res = requests.get(f"{BASE_URL}/debts/person/{encoded_name}/all", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching all debts for {person_name}: {e}")
        return []

# --- NEW FUNCTION ---
def get_all_settled_debts_by_person(person_name):
    """Fetches all settled debts for a person, regardless of currency."""
    try:
        encoded_name = urllib.parse.quote(person_name)
        res = requests.get(f"{BASE_URL}/debts/person/{encoded_name}/all/settled", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching all settled debts for {person_name}: {e}")
        return []


def get_debt_details(debt_id):
    try:
        res = requests.get(f"{BASE_URL}/debts/{debt_id}", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debt details: {e}")
        return None

# --- NEW FUNCTION ---
def cancel_debt(debt_id):
    """Sends a POST request to cancel a debt and reverse its transaction."""
    try:
        res = requests.post(f"{BASE_URL}/debts/{debt_id}/cancel", timeout=15)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error canceling debt: {e}")
        try:
            return e.response.json()
        except:
            return {'error': 'A network error occurred.'}

# --- NEW FUNCTION ---
def update_debt(debt_id, data):
    """Sends a PUT request to update a debt's person or purpose."""
    try:
        res = requests.put(f"{BASE_URL}/debts/{debt_id}", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error updating debt: {e}")
        try:
            return e.response.json()
        except:
            return {'error': 'A network error occurred.'}


def record_lump_sum_repayment(person_name, currency, amount, debt_type, timestamp=None):
    """ --- THIS FUNCTION HAS BEEN MODIFIED --- """
    try:
        encoded_currency = urllib.parse.quote(currency)
        url = f"{BASE_URL}/debts/person/{encoded_currency}/repay"
        payload = {
            'amount': amount, 
            'type': debt_type,
            'person': person_name
        }
        # --- FIX: Add timestamp to payload if it exists ---
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


def update_exchange_rate(rate):
    try:
        res = requests.post(f"{BASE_URL}/settings/rate", json={'rate': rate}, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error updating rate: {e}")
        return None


def add_transaction(data):
    try:
        res = requests.post(f"{BASE_URL}/transactions/", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error adding transaction: {e}")
        return None


def get_recent_transactions():
    try:
        res = requests.get(f"{BASE_URL}/transactions/recent", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching recent transactions: {e}")
        return []


def get_transaction_details(tx_id):
    try:
        res = requests.get(f"{BASE_URL}/transactions/{tx_id}", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching transaction details: {e}")
        return None


def update_transaction(tx_id, data):
    """Sends a PUT request to update a transaction."""
    try:
        res = requests.put(f"{BASE_URL}/transactions/{tx_id}", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error updating transaction: {e}")
        return None


def delete_transaction(tx_id):
    try:
        res = requests.delete(f"{BASE_URL}/transactions/{tx_id}", timeout=10)
        res.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"API Error deleting transaction: {e}")
        return False


def get_detailed_report(start_date=None, end_date=None):
    """Fetches detailed report data (income, expense, net) from the API."""
    try:
        params = {}
        if start_date and end_date:
            params['start_date'] = start_date.isoformat()
            params['end_date'] = end_date.isoformat()

        res = requests.get(f"{BASE_URL}/analytics/report/detailed", params=params, timeout=15)
        if res.status_code == 200:
            return res.json()
        return None
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching detailed report: {e}")
        return None


def get_spending_habits(start_date, end_date):
    """Fetches spending habits analysis from the API."""
    try:
        params = {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
        res = requests.get(f"{BASE_URL}/analytics/habits", params=params, timeout=20)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching spending habits: {e}")
        return None


def get_debt_analysis():
    """Fetches debt analysis data from the API."""
    try:
        res = requests.get(f"{BASE_URL}/debts/analysis", timeout=15)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debt analysis: {e}")
        return None


def search_transactions_for_management(params):
    """Sends a POST request to get a list of transactions for editing."""
    try:
        res = requests.post(f"{BASE_URL}/transactions/search", json=params, timeout=20)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error searching transactions for management: {e}")
        return []


def sum_transactions_for_analytics(params):
    """Sends a POST request to get a sum of transactions for analytics."""
    try:
        res = requests.post(f"{BASE_URL}/analytics/search", json=params, timeout=20)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error summing transactions: {e}")
        return None
