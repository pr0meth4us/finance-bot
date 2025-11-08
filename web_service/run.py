import os
import certifi
from pymongo import MongoClient
import requests
import json
from app import create_app
from app.config import Config  # Import Config to get the URI

# --- STARTUP DIAGNOSTIC ---
print("--- [run.py] STARTING NETWORK DIAGNOSTICS ---")

# --- Test 1: Pymongo (old method, for scheduled jobs) ---
print("--- [run.py] Test 1: Pymongo Connection (Port 27017) ---")
URI = Config.MONGODB_URI
DB_NAME = Config.DB_NAME

if not URI:
    print("[run.py] Pymongo: MONGODB_URI environment variable is NOT SET.")
else:
    print(f"[run.py] Pymongo: Connecting to: {URI[:15]}.../{DB_NAME}")
    try:
        client = MongoClient(
            URI,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000
        )
        result = client.admin.command('ping')
        print(f"[run.py] Pymongo: DIAGNOSTIC SUCCESS: {result}")
        client.close()
    except Exception as e:
        print(f"[run.py] Pymongo: !!! DIAGNOSTIC FAILED !!!")
        print(f"[run.py] Pymongo: Error: {e}")
print("--- [run.py] End of Pymongo Test ---")


# --- Test 2: Data API (new method, for app routes) ---
print("--- [run.py] Test 2: Atlas Data API (HTTPS Port 443) ---")
API_URL = Config.DATA_API_URL
API_KEY = Config.DATA_API_KEY

if not API_URL or not API_KEY:
    print("[run.py] Data API: DATA_API_URL or DATA_API_KEY is NOT SET.")
else:
    print(f"[run.py] Data API: Pinging endpoint: {API_URL}/action/findOne")
    headers = {
        'Content-Type': 'application/json',
        'api-key': API_KEY,
        'Accept': 'application/json'
    }
    data = {
        "dataSource": "expTracker",
        "database": "expTracker",
        "collection": "users",
        "filter": {"telegram_user_id": "00000"} # Dummy user
    }
    try:
        res = requests.post(f"{API_URL}/action/findOne", headers=headers, json=data, timeout=10)
        res.raise_for_status()
        print(f"[run.py] Data API: DIAGNOSTIC SUCCESS: {res.json()}")
    except Exception as e:
        print(f"[run.py] Data API: !!! DIAGNOSTIC FAILED !!!")
        print(f"[run.py] Data API: Error: {e}")

print("--- [run.py] END OF NETWORK DIAGNOSTICS ---")
print("--- [run.py] Starting Flask app... ---")

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)