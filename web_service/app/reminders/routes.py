from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
# This import is now needed for the dynamically scheduled job
from app import send_telegram_message

reminders_bp = Blueprint('reminders', __name__, url_prefix='/reminders')


@reminders_bp.route('/', methods=['POST'])
def add_reminder():
    data = request.json
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
        id=f"reminder_{data['chat_id']}_{datetime.now().timestamp()}",  # Unique job ID
        name=f"Reminder for {data['chat_id']}"
    )

    print(f"Scheduled a reminder for {data['chat_id']} at {reminder_datetime}")

    return jsonify({'message': 'Reminder scheduled successfully'}), 201