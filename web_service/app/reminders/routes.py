import requests
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from app.config import Config

reminders_bp = Blueprint('reminders', __name__, url_prefix='/reminders')


def send_reminder_job(chat_id, message):
    """The job that sends the reminder message via the Telegram API."""
    token = Config.TELEGRAM_TOKEN
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': f"🔔 Reminder:\n\n{message}"
    }
    try:
        requests.post(url, json=payload, timeout=10)
        print(f"Successfully sent reminder to chat_id: {chat_id}")
    except Exception as e:
        print(f"Failed to send reminder to {chat_id}: {e}")


@reminders_bp.route('/add', methods=['POST'])
def add_reminder():
    data = request.json
    if not all(k in data for k in ['chat_id', 'message', 'remind_at']):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        chat_id = data['chat_id']
        message = data['message']
        remind_at_dt = datetime.fromisoformat(data['remind_at'])

        # Use a unique ID for the job to prevent duplicates
        job_id = f"reminder_{chat_id}_{int(remind_at_dt.timestamp())}"

        current_app.scheduler.add_job(
            send_reminder_job,
            trigger='date',
            run_date=remind_at_dt,
            args=[chat_id, message],
            id=job_id,
            replace_existing=True
        )

        return jsonify({'message': 'Reminder scheduled successfully', 'job_id': job_id}), 201

    except Exception as e:
        current_app.logger.error(f"Failed to schedule reminder: {e}")
        return jsonify({'error': 'Failed to schedule reminder'}), 500