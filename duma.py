from pymongo import MongoClient
import certifi

uri = "mongodb+srv://koyeb:azsuPHhIKVqqtExh@exptracker.dtmvhzp.mongodb.net/expTracker?retryWrites=true&w=majority"

client = MongoClient(uri, tls=True, tlsCAFile=certifi.where())
print(client.admin.command('ping'))  # Should print {'ok': 1.0}