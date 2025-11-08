import os
import certifi
from pymongo import MongoClient
from app import create_app
from app.config import Config  # Import Config to get the URI

# --- STARTUP DIAGNOSTIC ---
# This code runs *before* the app starts, just like duma.py
print("--- [run.py] STARTING NETWORK DIAGNOSTIC ---")
URI = Config.MONGODB_URI
DB_NAME = Config.DB_NAME

if not URI:
    print("[run.py] DIAGNOSTIC FAILED: MONGODB_URI environment variable is NOT SET.")
else:
    print(f"[run.py] Connecting to: {URI[:15]}.../{DB_NAME}")
    print(f"[run.py] Using CAFile: {certifi.where()}")
    try:
        client = MongoClient(
            URI,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000  # 10-second timeout for this test
        )
        # The 'ping' command is the simplest way to test the connection
        result = client.admin.command('ping')
        print(f"[run.py] DIAGNOSTIC SUCCESS: MongoDB admin ping result: {result}")

        # Test DB access
        db = client[DB_NAME]
        collections = db.list_collection_names()
        print(f"[run.py] DIAGNOSTIC SUCCESS: Found {len(collections)} collections in '{DB_NAME}'.")

    except Exception as e:
        print(f"[run.py] !!! DIAGNOSTIC FAILED !!!")
        print(f"[run.py] Error: {e}")
        print("[run.py] This confirms the container CANNOT reach the MongoDB server.")
        print("[run.py] This is a container networking issue (e.g., Koyeb egress policy).")

print("--- [run.py] END OF NETWORK DIAGNOSTIC ---")
print("--- [run.py] Starting Flask app... ---")

app = create_app()

if __name__ == '__main__':
    # Use Gunicorn (or another WSGI server) in production
    # For this debug step, we continue to run Flask's dev server
    app.run(host='0.0.0.0', port=8000)