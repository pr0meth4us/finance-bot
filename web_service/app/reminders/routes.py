from flask import Blueprint, request, jsonify, current_app, g
from datetime import datetime
from bson import ObjectId

from app import send_telegram_message
from app.utils.db import reminders_collection
from app.utils.auth import auth_required

reminders_bp = Blueprint('reminders', __name__, url_prefix='/reminders')

@reminders_bp.route('/', methods=['POST'])
@auth_required(min_role="user")
def add_reminder():
    try:
        account_id = ObjectId(g.account_id)
    except Exception:
        return jsonify({'error': 'Invalid account_id format'}), 400

    data = request.json
    if not all(k in data for k in ['purpose', 'reminder_datetime', 'chat_id']):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        remind_dt = datetime.fromisoformat(data['reminder_datetime'])
    except ValueError:
        return jsonify({'error': 'Invalid datetime format'}), 400

    scheduler = current_app.scheduler
    token = current_app.config['TELEGRAM_TOKEN']
    message = f"🔔 Reminder:\n\n{data['purpose']}"

    # Schedule job
    scheduler.add_job(
        send_telegram_message,
        trigger='date',
        run_date=remind_dt,
        args=[data['chat_id'], message, token],
        id=f"reminder_{account_id}_{datetime.now().timestamp()}",
        name=f"Reminder for user {account_id}"
    )

    # Log to DB
    reminders_collection().insert_one({
        "account_id": account_id,
        "purpose": data['purpose'],
        "chat_id": data['chat_id'],
        "reminder_datetime": remind_dt,
        "created_at": datetime.now()
    })

    current_app.logger.info(f"Scheduled reminder for {account_id} at {remind_dt}")
    return jsonify({'message': 'Reminder scheduled successfully'}), 201