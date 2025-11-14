# --- web_service/app/reminders/routes.py (Refactored) ---
"""
Handles scheduling reminders for users.
All endpoints are multi-tenant and require a valid user_id.
"""
from flask import Blueprint, request, jsonify, current_app, g
from datetime import datetime
from app import send_telegram_message
from app.utils.db import reminders_collection
# --- REFACTOR: Import new auth decorator ---
from app.utils.auth import auth_required

reminders_bp = Blueprint('reminders', __name__, url_prefix='/reminders')


@reminders_bp.route('/', methods=['POST'])
@auth_required(min_role="user") # --- REFACTOR: Add decorator ---
def add_reminder():
    """Schedules a new reminder for the authenticated user."""
    data = request.json

    # --- REFACTOR: Get account_id from g ---
    account_id = g.account_id
    # ---

    if not all(k in data for k in ['purpose', 'reminder_datetime', 'chat_id']):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        reminder_datetime = datetime.fromisoformat(data['reminder_datetime'])
    except ValueError:
        return jsonify({'error': 'Invalid datetime format'}), 400

    scheduler = current_app.scheduler
    token = current_app.config['TELEGRAM_TOKEN']
    message_text = f"🔔 Reminder:\n\n{data['purpose']}"

    # Schedule a one-off job to send the reminder at the specified time
    scheduler.add_job(
        send_telegram_message,
        trigger='date',
        run_date=reminder_datetime,
        args=[data['chat_id'], message_text, token],
        id=f"reminder_{account_id}_{datetime.now().timestamp()}",  # Unique job ID
        name=f"Reminder for user {account_id}"
    )

    # Log the reminder in the database
    reminders_collection().insert_one({
        "account_id": account_id, # <-- REFACTOR
        "purpose": data['purpose'],
        "chat_id": data['chat_id'],
        "reminder_datetime": reminder_datetime,
        "created_at": datetime.now()
    })

    print(f"Scheduled a reminder for user {account_id} at {reminder_datetime}")
    return jsonify({'message': 'Reminder scheduled successfully'}), 201