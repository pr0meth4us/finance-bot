# --- Start of new file: web_service/app/utils/auth.py ---
"""
Reusable authentication utility functions for the web service.
"""
from flask import request, jsonify
from bson import ObjectId


def get_user_id_from_request():
    """
    Gets the user_id from the request body (JSON) or query parameters.

    This function ensures a 'user_id' is present and valid in all
    user-specific API calls.

    Returns:
        tuple: (user_id_obj, None) on success, or (None, error_response) on failure.
    """
    user_id_str = None
    if request.is_json:
        user_id_str = request.json.get('user_id')

    if not user_id_str:
        user_id_str = request.args.get('user_id')

    if not user_id_str:
        # 401 Unauthorized is the appropriate code for missing credentials
        return None, (jsonify({'error': 'user_id is required'}), 401)

    try:
        # Validate that it's a proper ObjectId and return the object
        user_id_obj = ObjectId(user_id_str)
        return user_id_obj, None
    except Exception:
        # 400 Bad Request for malformed ID
        return None, (jsonify({'error': 'Invalid user_id format'}), 400)
# --- End of new file ---