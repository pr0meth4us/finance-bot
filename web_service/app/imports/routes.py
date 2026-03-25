import uuid
import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g
from pymongo.errors import BulkWriteError
from app.utils.auth import auth_required
from app.utils.db import get_db
from app.parsers.bank_statements import parse_statement, UnsupportedBankError

log = logging.getLogger(__name__)

# FIX: Added url_prefix='/imports' so the routes mount correctly
imports_bp = Blueprint('imports', __name__, url_prefix='/imports')


@imports_bp.route('/upload', methods=['POST'])
@auth_required(min_role="user")
def upload_statement():
    """
    Accepts a CSV or XLSX file, parses it, and stores it in a temporary session
    for the user to review on the Web Dashboard.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected for uploading"}), 400

    if not (file.filename.lower().endswith('.csv') or file.filename.lower().endswith('.xlsx')):
        return jsonify({"error": "Only .csv and .xlsx files are supported"}), 400

    db = get_db()

    # Fetch user's registered bank names for self-transfer detection
    user_settings = db.settings.find_one({"account_id": g.account_id}) or {}
    bank_names = user_settings.get("settings", {}).get("bank_names", {})

    try:
        file_bytes = file.read()
        parsed_transactions = parse_statement(file_bytes, file.filename, user_bank_names=bank_names)

        if not parsed_transactions:
            return jsonify({"error": "No valid transactions found in the file."}), 400

        # Generate a unique session ID for the Next.js review page
        session_id = str(uuid.uuid4())

        # Store in pending_imports collection
        db.pending_imports.insert_one({
            "session_id": session_id,
            "account_id": g.account_id,
            "filename": file.filename,
            "transactions": parsed_transactions,
            "created_at": datetime.now(timezone.utc)
        })

        return jsonify({
            "message": "File parsed successfully.",
            "session_id": session_id,
            "transaction_count": len(parsed_transactions)
        }), 200

    except UnsupportedBankError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        log.error(f"Error parsing uploaded file {file.filename} for account {g.account_id}: {str(e)}")
        return jsonify({"error": "An error occurred while processing the file."}), 500


@imports_bp.route('/<session_id>', methods=['GET'])
@auth_required(min_role="user")
def get_pending_import(session_id):
    """
    Retrieves the parsed transactions for a given session ID so the frontend can display them.
    """
    db = get_db()
    session_data = db.pending_imports.find_one({"session_id": session_id, "account_id": g.account_id})

    if not session_data:
        return jsonify({"error": "Import session not found or expired."}), 404

    # Format dates to ISO strings for JSON serialization
    transactions = session_data.get('transactions', [])
    for txn in transactions:
        if isinstance(txn.get('date'), datetime):
            txn['date'] = txn['date'].isoformat()

    return jsonify({
        "session_id": session_data["session_id"],
        "filename": session_data.get("filename", "Unknown"),
        "transactions": transactions
    }), 200


@imports_bp.route('/<session_id>/confirm', methods=['POST'])
@auth_required(min_role="user")
def confirm_import(session_id):
    """
    Receives a list of approved bank_reference_ids from the frontend,
    inserts the matching transactions into the main DB, and deletes the session.
    """
    data = request.get_json()
    if not data or 'approved_reference_ids' not in data:
        return jsonify({"error": "Missing approved_reference_ids in payload."}), 400

    approved_ids = set(data['approved_reference_ids'])
    db = get_db()

    session_data = db.pending_imports.find_one({"session_id": session_id, "account_id": g.account_id})
    if not session_data:
        return jsonify({"error": "Import session not found or expired."}), 404

    transactions_to_insert = []
    for txn in session_data.get('transactions', []):
        if txn.get('bank_reference_id') in approved_ids:
            # Ensure standard transaction fields are populated
            txn['account_id'] = g.account_id
            txn['status'] = 'completed'
            txn['timestamp'] = txn['date']  # Use the parsed date as the timestamp
            txn['created_at'] = datetime.now(timezone.utc)
            del txn['date']  # Remove the temporary date key

            transactions_to_insert.append(txn)

    inserted_count = 0
    duplicate_count = 0

    if transactions_to_insert:
        try:
            # ordered=False allows Mongo to continue inserting the rest of the batch
            # even if it hits a DuplicateKeyError on a specific document.
            result = db.transactions.insert_many(transactions_to_insert, ordered=False)
            inserted_count = len(result.inserted_ids)
        except BulkWriteError as bwe:
            # bwe.details contains information about which inserts succeeded and which failed
            inserted_count = bwe.details.get('nInserted', 0)
            # Count how many failed specifically due to duplicate key (code 11000)
            duplicate_count = sum(1 for err in bwe.details.get('writeErrors', []) if err['code'] == 11000)

            log.warning(
                f"Imported {inserted_count} txns, but skipped {duplicate_count} duplicates for session {session_id}.")

    # Clean up the temporary session
    db.pending_imports.delete_one({"session_id": session_id})

    return jsonify({
        "message": "Import completed.",
        "inserted_count": inserted_count,
        "duplicate_skipped_count": duplicate_count
    }), 200