from functools import wraps
from flask import request, jsonify, g
from web_service.app.db import db_client

def auth_required(f):
    """
    Decorator to ensure the request contains a valid telegram_user_id
    and that the user has an 'active' subscription or 'is_admin' role.

    The user's MongoDB document and telegram_user_id are stored on
    flask.g for access in the route function.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Extract user_id from the JSON payload (standard for bot API)
        data = request.json or request.form.to_dict()
        user_id = data.get('telegram_user_id')

        if not user_id:
            return jsonify({
                'error': 'Authentication failed: Missing telegram_user_id in request payload.'
            }), 401

        # 2. Look up the user in the database
        user = db_client.db.users.find_one({"telegram_user_id": str(user_id)})

        if not user:
            return jsonify({
                'error': f'Authentication failed: User {user_id} not found.'
            }), 404

        # 3. Check for subscription status or admin role
        is_active_subscriber = user.get('subscription_status') == 'active'
        is_admin = user.get('is_admin', False)

        if not (is_active_subscriber or is_admin):
            return jsonify({
                'error': 'Access Denied: Your subscription is not active. Please renew to continue access.'
            }), 403

        # 4. Inject user data into Flask's global context (g) for route handlers
        g.user = user
        g.user_id = str(user_id) # Store as string for consistency in queries

        # Execute the original route function
        return f(*args, **kwargs)

    return decorated_function