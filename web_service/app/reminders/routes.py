from flask import Blueprint, request, jsonify, current_app
from datetime import datetime

reminders_bp = Blueprint('reminders', __name__, url_prefix='/reminders')

@reminders_bp.route('/', methods=['POST'])
def add_reminder():
    data = request.json
    if not all(k in data for k in ['purpose', 'reminder_date', 'chat_id']):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        reminder_date = datetime.fromisoformat(data['reminder_date'])
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    reminder = {
        "purpose": data['purpose'],
        "reminder_date": reminder_date,
        "chat_id": data['chat_id'],
        "created_at": datetime.utcnow()
    }

    result = current_app.db.reminders.insert_one(reminder)
    return jsonify({'message': 'Reminder set successfully', 'id': str(result.inserted_id)}), 201