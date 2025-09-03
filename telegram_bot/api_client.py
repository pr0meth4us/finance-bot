import os
import requests
from dotenv import load_dotenv
import urllib.parse

load_dotenv()
BASE_URL = os.getenv("WEB_SERVICE_URL")


def get_balance_summary():
    try:
        res = requests.get(f"{BASE_URL}/summary/balance", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching summary: {e}")
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
    """Sends a new reminder to the backend."""
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


def get_debts_by_person_and_currency(person_name, currency):
    """Fetches all open debts for a specific person and currency."""
    try:
        encoded_name = urllib.parse.quote(person_name)
        res = requests.get(f"{BASE_URL}/debts/person/{encoded_name}/{currency}", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debts for {person_name} ({currency}): {e}")
        return []


def get_debt_details(debt_id):
    try:
        res = requests.get(f"{BASE_URL}/debts/{debt_id}", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debt details: {e}")
        return None


def record_lump_sum_repayment(person_name, currency, amount):
    """Records a lump-sum repayment for a person in a specific currency."""
    try:
        encoded_name = urllib.parse.quote(person_name)
        url = f"{BASE_URL}/debts/person/{encoded_name}/{currency}/repay"
        payload = {'amount': amount}
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


def delete_transaction(tx_id):
    try:
        res = requests.delete(f"{BASE_URL}/transactions/{tx_id}", timeout=10)
        res.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"API Error deleting transaction: {e}")
        return False


def get_chart(start_date=None, end_date=None):
    try:
        params = {}
        if start_date and end_date:
            params['start_date'] = start_date.isoformat()
            params['end_date'] = end_date.isoformat()

        res = requests.get(f"{BASE_URL}/analytics/report/chart", params=params, timeout=15)
        if res.status_code == 200:
            return res.content
        return None
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching chart: {e}")
        return None