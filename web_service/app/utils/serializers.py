# --- web_service/app/utils/serializers.py (New) ---
"""
Helper functions to serialize MongoDB documents for JSON responses.
"""
from bson import ObjectId
from datetime import datetime

def serialize_profile(doc):
    """Serializes a settings profile doc, converting ObjectId and datetime."""
    if '_id' in doc and isinstance(doc['_id'], ObjectId):
        doc['_id'] = str(doc['_id'])
    if 'account_id' in doc and isinstance(doc['account_id'], ObjectId):
        doc['account_id'] = str(doc['account_id'])
    if 'created_at' in doc and isinstance(doc['created_at'], datetime):
        doc['created_at'] = doc['created_at'].isoformat()
    return doc
# --- End of new file ---