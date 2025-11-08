# --- Start of modified file: web_service/app/reminders/routes.py ---
"""
Handles scheduling reminders for users.
All endpoints are multi-tenant and require a valid user_id.
"""
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
# --- MODIFICATION: Import current_app, remove get_db ---
from app import send_telegram_message
from app.utils.auth import get_user_id_from_request

reminders_bp = Blueprint('reminders', __name__, url_prefix='/reminders')


@reminders_bp.route('/', methods=['POST'])
def add_reminder():
    """Schedules a new reminder for the authenticated user."""
    db = current_app.db # <-- MODIFICATION
    data = request.json

    # --- MODIFICATION: Authenticate user ---
    user_id, error = get_user_id_from_request()
    if error: return error
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
        id=f"reminder_{user_id}_{datetime.now().timestamp()}",  # Unique job ID
        name=f"Reminder for user {user_id}"
    )

    # --- MODIFICATION: Log the reminder in the database ---
    db.reminders.insert_one({
        "user_id": user_id,
        "purpose": data['purpose'],
        "chat_id": data['chat_id'],
        "reminder_datetime": reminder_datetime,
        "created_at": datetime.now()
    })
    # ---

    print(f"Scheduled a reminder for user {user_id} at {reminder_datetime}")
    return jsonify({'message': 'Reminder scheduled successfully'}), 201
# --- End of modified file ---