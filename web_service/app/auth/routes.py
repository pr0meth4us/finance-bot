from flask import Blueprint, request, jsonify, current_app
from web_service.app.db import db_client
from datetime import datetime
from zoneinfo import ZoneInfo

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
UTC_TZ = ZoneInfo("UTC")

@auth_bp.route('/find_or_create', methods=['POST'])
def find_or_create_user():
    """
    Handles initial user check/onboarding.
    - Finds an existing user.
    - Creates a new user with 'inactive' status if they don't exist.
    - Checks for super-admin status (hardcoded in Config/DB init).
    """
    data = request.json
    telegram_user_id = data.get('telegram_user_id')

    if not telegram_user_id:
        return jsonify({'error': 'Missing telegram_user_id'}), 400

    telegram_user_id = str(telegram_user_id)
    db = db_client.db

    # 1. Find the user
    user = db.users.find_one({"telegram_user_id": telegram_user_id})

    # 2. Create user if not found
    if not user:
        # Default settings for a brand new user
        new_user_data = {
            "telegram_user_id": telegram_user_id,
            # All new users start as inactive, requiring subscription payment/admin activation
            "subscription_status": "inactive",
            "is_admin": False,
            "created_at": datetime.now(UTC_TZ),
            "updated_at": datetime.now(UTC_TZ)
        }
        db.users.insert_one(new_user_data)

        # Insert minimal settings document to avoid errors later (will be populated on onboarding)
        db.settings.insert_one({
            "user_id": telegram_user_id,
            "language": "en", # Default language
            "is_onboarded": False, # New field for onboarding flow
            "created_at": datetime.now(UTC_TZ),
            "updated_at": datetime.now(UTC_TZ)
        })

        user = db.users.find_one({"telegram_user_id": telegram_user_id})

        return jsonify({
            'message': 'New user created. Subscription inactive.',
            'user_id': telegram_user_id,
            'is_admin': False,
            'subscription_status': 'inactive',
            'is_onboarded': False
        }), 201

    # 3. If user exists, check their status and settings
    settings = db_client.get_user_settings(telegram_user_id)
    is_onboarded = settings.get('is_onboarded', False) if settings else False

    return jsonify({
        'message': 'User found.',
        'user_id': telegram_user_id,
        'is_admin': user.get('is_admin', False),
        'subscription_status': user.get('subscription_status'),
        'is_onboarded': is_onboarded
    }), 200

# --- NEW ADMIN ENDPOINTS (Skeleton - Full implementation in Phase 4) ---
from flask_cors import CORS # Will need this for the web dashboard/admin dashboard

@auth_bp.route('/check_admin', methods=['POST'])
def check_admin_status():
    """Simple check for admin status for the Admin Dashboard frontend."""
    data = request.json
    telegram_user_id = data.get('telegram_user_id')

    if not telegram_user_id:
        return jsonify({'error': 'Missing telegram_user_id'}), 400

    user = db_client.db.users.find_one({"telegram_user_id": str(telegram_user_id)})

    if user and user.get('is_admin', False):
        return jsonify({'is_admin': True}), 200

    return jsonify({'is_admin': False}), 403