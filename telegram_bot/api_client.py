import os
import requests
from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("WEB_SERVICE_URL")

# --- Debt Functions ---
def add_debt(data):
    try:
        res = requests.post(f"{BASE_URL}/debts/", json=data)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error adding debt: {e}")
        return None

def get_open_debts():
    try:
        res = requests.get(f"{BASE_URL}/debts/")
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching debts: {e}")
        return []

def settle_debt(debt_id):
    try:
        res = requests.post(f"{BASE_URL}/debts/{debt_id}/settle")
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error settling debt: {e}")
        return None

# --- Other Functions ---
def update_exchange_rate(rate):
    try:
        res = requests.post(f"{BASE_URL}/settings/rate", json={'rate': rate})
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error updating rate: {e}")
        return None

def add_transaction(data):
    try:
        res = requests.post(f"{BASE_URL}/transactions/", json=data)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error adding transaction: {e}")
        return None

def get_recent_transactions():
    try:
        res = requests.get(f"{BASE_URL}/transactions/recent")
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching recent transactions: {e}")
        return []

def delete_transaction(tx_id):
    try:
        res = requests.delete(f"{BASE_URL}/transactions/{tx_id}")
        res.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"API Error deleting transaction: {e}")
        return False

def get_chart():
    try:
        res = requests.get(f"{BASE_URL}/analytics/report/chart")
        if res.status_code == 200:
            return res.content
        return None
    except requests.exceptions.RequestException as e:
        print(f"API Error fetching chart: {e}")
        return None