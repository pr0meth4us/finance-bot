# --- Start of modified file: telegram_bot/api_client.py ---
import os
import requests
from dotenv import load_dotenv
import urllib.parse

load_dotenv()
BASE_URL = os.getenv("WEB_SERVICE_URL")


# --- NEW AUTH FUNCTION ---
# api_client.py
def find_or_create_user(telegram_id):
    try:
        data = {"telegram_user_id": str(telegram_id)}
        res = requests.post(f"{BASE_URL}/auth/find_or_create", json=data, timeout=10)
        if res.status_code == 200:
            return res.json()
        if res.status_code == 403:
            return res.json()
        print(f"[AUTH] HTTP {res.status_code}: {res.text}")
        return {"error": f"Auth API error ({res.status_code})"}
    except requests.exceptions.RequestException as e:
        print(f"[AUTH] Network error: {e}")
        return {"error": "Network error reaching Auth API"}



def get_detailed_summary(user_id):
    """Fetches detailed summary for a specific user."""
    try:
        res = requests.get(
            f"{BASE_URL}/summary/detailed",
            params={'user_id': user_id},
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching detailed summary: {e}")
        return None


def add_debt(data, user_id):
    """Adds a new debt for a specific user."""
    try:
        data['user_id'] = user_id
        res = requests.post(f"{BASE_URL}/debts/", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error adding debt: {e}")
        return None


def add_reminder(data, user_id):
    """Adds a new reminder for a specific user."""
    try:
        data['user_id'] = user_id
        res = requests.post(f"{BASE_URL}/reminders/", json=data, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error adding reminder: {e}")
        return None


def get_open_debts(user_id):
    """Fetches open debts for a specific user."""
    try:
        res = requests.get(
            f"{BASE_URL}/debts/", params={'user_id': user_id}, timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debts: {e}")
        return []


# --- NEW FUNCTION FOR DEBT EXPORT ---
def get_open_debts_export(user_id):
    """Fetches a flat list of all open debts for export."""
    try:
        res = requests.get(
            f"{BASE_URL}/debts/export/open",
            params={'user_id': user_id},
            timeout=15
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debts for export: {e}")
        return []
# --- END NEW FUNCTION ---


def get_settled_debts_grouped(user_id):
    """Fetches settled debts for a specific user."""
    try:
        res = requests.get(
            f"{BASE_URL}/debts/list/settled",
            params={'user_id': user_id},
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching settled debts: {e}")
        return []


def get_debts_by_person_and_currency(person_name, currency, user_id):
    """Fetches debts by person/currency for a specific user."""
    try:
        encoded_name = urllib.parse.quote(person_name)
        res = requests.get(
            f"{BASE_URL}/debts/person/{encoded_name}/{currency}",
            params={'user_id': user_id},
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(
            f"API Error fetching debts for {person_name} ({currency}): {e}"
        )
        return []


def get_all_debts_by_person(person_name, user_id):
    """Fetches all open debts for a person, for a specific user."""
    try:
        encoded_name = urllib.parse.quote(person_name)
        res = requests.get(
            f"{BASE_URL}/debts/person/{encoded_name}/all",
            params={'user_id': user_id},
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching all debts for {person_name}: {e}")
        return []


def get_all_settled_debts_by_person(person_name, user_id):
    """Fetches all settled debts for a person, for a specific user."""
    try:
        encoded_name = urllib.parse.quote(person_name)
        res = requests.get(
            f"{BASE_URL}/debts/person/{encoded_name}/all/settled",
            params={'user_id': user_id},
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(
            f"API Error fetching all settled debts for {person_name}: {e}"
        )
        return []


def get_debt_details(debt_id, user_id):
    """Fetches debt details for a specific user."""
    try:
        res = requests.get(
            f"{BASE_URL}/debts/{debt_id}",
            params={'user_id': user_id},
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debt details: {e}")
        return None


def cancel_debt(debt_id, user_id):
    """Cancels a debt for a specific user."""
    try:
        res = requests.post(
            f"{BASE_URL}/debts/{debt_id}/cancel",
            json={'user_id': user_id},
            timeout=15
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error canceling debt: {e}")
        try:
            return e.response.json()
        except Exception:
            return {'error': 'A network error occurred.'}


def update_debt(debt_id, data, user_id):
    """Updates a debt for a specific user."""
    try:
        data['user_id'] = user_id
        res = requests.put(
            f"{BASE_URL}/debts/{debt_id}", json=data, timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error updating debt: {e}")
        try:
            return e.response.json()
        except Exception:
            return {'error': 'A network error occurred.'}


def record_lump_sum_repayment(
        person_name, currency, amount, debt_type, user_id, timestamp=None
):
    """Records a lump sum repayment for a specific user."""
    try:
        encoded_currency = urllib.parse.quote(currency)
        url = f"{BASE_URL}/debts/person/{encoded_currency}/repay"
        payload = {
            'amount': amount,
            'type': debt_type,
            'person': person_name,
            'user_id': user_id
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
        except Exception:
            return {'error': 'A network error occurred.'}


def update_exchange_rate(rate, user_id):
    """Updates the *user's* fixed rate preference."""
    try:
        res = requests.post(
            f"{BASE_URL}/settings/rate",
            json={'rate': rate, 'user_id': user_id},
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error updating rate: {e}")
        return None


def get_exchange_rate(user_id):
    """Fetches the exchange rate based on user's preference."""
    try:
        res = requests.get(
            f"{BASE_URL}/settings/rate",
            params={'user_id': user_id},
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching rate: {e}")
        return None


def add_transaction(data, user_id):
    """Adds a transaction for a specific user."""
    try:
        data['user_id'] = user_id
        res = requests.post(
            f"{BASE_URL}/transactions/", json=data, timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error adding transaction: {e}")
        return None


def get_recent_transactions(user_id):
    """Fetches recent transactions for a specific user."""
    try:
        res = requests.get(
            f"{BASE_URL}/transactions/recent",
            params={'user_id': user_id},
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching recent transactions: {e}")
        return []


def get_transaction_details(tx_id, user_id):
    """Fetches transaction details for a specific user."""
    try:
        res = requests.get(
            f"{BASE_URL}/transactions/{tx_id}",
            params={'user_id': user_id},
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching transaction details: {e}")
        return None


def update_transaction(tx_id, data, user_id):
    """Updates a transaction for a specific user."""
    try:
        data['user_id'] = user_id
        res = requests.put(
            f"{BASE_URL}/transactions/{tx_id}", json=data, timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error updating transaction: {e}")
        return None


def delete_transaction(tx_id, user_id):
    """Deletes a transaction for a specific user."""
    try:
        res = requests.delete(
            f"{BASE_URL}/transactions/{tx_id}",
            json={'user_id': user_id},
            timeout=10
        )
        res.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"API Error deleting transaction: {e}")
        return False


def get_detailed_report(user_id, start_date=None, end_date=None):
    """Fetches a detailed report for a specific user."""
    try:
        params = {'user_id': user_id}
        if start_date and end_date:
            params['start_date'] = start_date.isoformat()
            params['end_date'] = end_date.isoformat()

        res = requests.get(
            f"{BASE_URL}/analytics/report/detailed",
            params=params,
            timeout=15
        )
        if res.status_code == 200:
            return res.json()
        return None
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching detailed report: {e}")
        return None


def get_spending_habits(user_id, start_date, end_date):
    """Fetches spending habits for a specific user."""
    try:
        params = {
            'user_id': user_id,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
        res = requests.get(
            f"{BASE_URL}/analytics/habits", params=params, timeout=20
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching spending habits: {e}")
        return None


def get_debt_analysis(user_id):
    """Fetches debt analysis for a specific user."""
    try:
        res = requests.get(
            f"{BASE_URL}/debts/analysis",
            params={'user_id': user_id},
            timeout=15
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debt analysis: {e}")
        return None


def search_transactions_for_management(params, user_id):
    """Searches transactions for a specific user."""
    try:
        params['user_id'] = user_id
        res = requests.post(
            f"{BASE_URL}/transactions/search", json=params, timeout=20
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error searching transactions for management: {e}")
        return []


def sum_transactions_for_analytics(params, user_id):
    """Sums transactions for a specific user."""
    try:
        params['user_id'] = user_id
        res = requests.post(
            f"{BASE_URL}/analytics/search", json=params, timeout=20
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error summing transactions: {e}")
        return None


# --- NEW SETTINGS FUNCTIONS ---

def get_user_settings(user_id):
    """Fetches all settings for a user."""
    try:
        res = requests.get(
            f"{BASE_URL}/settings/", params={'user_id': user_id}, timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching settings: {e}")
        return None


def update_initial_balance(user_id, currency, amount):
    """Updates the user's initial balance for one currency."""
    try:
        payload = {
            'user_id': user_id,
            'currency': currency,
            'amount': amount
        }
        res = requests.post(
            f"{BASE_URL}/settings/balance", json=payload, timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error updating initial balance: {e}")
        return None


def add_category(user_id, cat_type, cat_name):
    """Adds a custom category for a user."""
    try:
        payload = {
            'user_id': user_id,
            'type': cat_type,
            'name': cat_name
        }
        res = requests.post(
            f"{BASE_URL}/settings/category", json=payload, timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error adding category: {e}")
        return None


def remove_category(user_id, cat_type, cat_name):
    """Removes a custom category for a user."""
    try:
        payload = {
            'user_id': user_id,
            'type': cat_type,
            'name': cat_name
        }
        res = requests.delete(
            f"{BASE_URL}/settings/category", json=payload, timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error removing category: {e}")
        return None

# --- End of modified file ---