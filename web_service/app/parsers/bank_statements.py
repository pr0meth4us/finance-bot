import io
import csv
import re
from datetime import datetime
import openpyxl


class UnsupportedBankError(Exception):
    """Raised when the uploaded file does not match known ABA or ACLEDA formats."""
    pass


def parse_statement(file_bytes, filename, user_bank_names=None):
    """
    Auto-detects the bank from the file headers and parses the transactions.
    Supports both .csv and .xlsx files.
    """
    if user_bank_names is None:
        user_bank_names = {}

    rows = _extract_rows(file_bytes, filename)

    if not rows:
        raise ValueError("The uploaded file is empty or could not be read.")

    # Flatten first 20 rows into a single uppercase string for signature detection
    sample_text = " ".join([" ".join(str(cell) for cell in row if cell) for row in rows[:20]]).upper()

    if "ACLBKHPP" in sample_text or ("ACLEDA" in sample_text and "ACCOUNT STATEMENT" in sample_text):
        return _parse_acleda(rows, user_bank_names.get('acleda', ''))
    elif "ACCOUNT ACTIVITY" in sample_text or "MONEY IN" in sample_text:
        return _parse_aba(rows, user_bank_names.get('aba', ''))
    else:
        raise UnsupportedBankError(
            "Could not detect bank. We currently only support ABA and ACLEDA statements in .csv or .xlsx format.")


def _extract_rows(file_bytes, filename):
    """Extracts rows from either an Excel workbook or a CSV file."""
    rows = []
    if filename.lower().endswith('.xlsx'):
        # read_only=True forces a lazy XML stream, preventing heavy DOM memory loads
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
        sheet = wb.active
        empty_row_count = 0

        for row in sheet.iter_rows(values_only=True):
            clean_row = ["" if cell is None else str(cell).strip() for cell in row]

            # Optimization: Stop processing if we hit 10 consecutive empty rows
            if not any(clean_row):
                empty_row_count += 1
                if empty_row_count > 10:
                    break
                continue

            empty_row_count = 0
            rows.append(clean_row)

        # Explicitly close to free the read-only memory buffer
        wb.close()
    else:
        # Standard CSV processing
        content = file_bytes.decode('utf-8', errors='replace')
        reader = csv.reader(io.StringIO(content))
        for row in reader:
            rows.append([cell.strip() for cell in row])

    return rows


def _parse_aba(rows, user_aba_name):
    """Parses ABA Bank statement format."""
    transactions = []
    header_found = False

    for row in rows:
        if len(row) < 8:
            continue

        if not header_found:
            if "Date" in row[0] and "Transaction Details" in row[1]:
                header_found = True
            continue

        date_str = row[0]
        desc = row[1]
        money_in = row[2].replace(',', '') if row[2] else ""
        money_out = row[4].replace(',', '') if row[4] else ""

        if not date_str or (not money_in and not money_out):
            continue

        try:
            dt = datetime.strptime(date_str, "%b %d, %Y")
        except ValueError:
            continue

        # Extract Reference ID
        ref_match = re.search(r'(?:REF#|HASH#)\s*([A-Z0-9]+)', desc)
        bank_ref = ref_match.group(1) if ref_match else None

        # Determine Amount and Type
        amount = 0.0
        currency = row[3] if money_in else row[5]  # Ccy column
        txn_type = "expense"

        if money_in:
            amount = float(money_in)
            txn_type = "income"
        elif money_out:
            amount = float(money_out)
            txn_type = "expense"

        # Self-Transfer Detection
        user_aba_name_upper = user_aba_name.upper()
        desc_upper = desc.upper()
        if user_aba_name_upper and user_aba_name_upper in desc_upper:
            if "TRANSFERRED TO" in desc_upper or "PAYMENT FROM" in desc_upper:
                txn_type = "transfer"

        transactions.append({
            "date": dt,
            "amount": amount,
            "currency": currency.upper() if currency else "USD",
            "type": txn_type,
            "description": desc,
            "bank_reference_id": f"ABA-{bank_ref}" if bank_ref else None,
            "source_bank": "ABA"
        })

    return transactions


def _parse_acleda(rows, user_acleda_name):
    """Parses ACLEDA Bank statement format."""
    transactions = []
    header_found = False

    for row in rows:
        if len(row) < 5:
            continue

        if not header_found:
            if "DATE" in row[0].upper() and "DESCRIPTIONS" in row[1].upper():
                header_found = True
            continue

        date_str = row[0]
        desc = row[1]
        cash_out = row[2].replace(',', '') if row[2] else ""
        cash_in = row[3].replace(',', '') if row[3] else ""

        if not date_str or (not cash_in and not cash_out):
            continue

        try:
            dt = datetime.strptime(date_str, "%b %d, %Y")
        except ValueError:
            continue

        # Extract Reference ID from description
        ref_match = re.search(r'(?:Ref\.|Order ID\s*)([0-9]+)', desc)
        bank_ref = ref_match.group(1) if ref_match else None

        # Determine Amount, Currency, and Type
        # ACLEDA amounts in the column are usually in the account's base currency (e.g., KHR)
        # But the description often holds the exact transaction currency (e.g., |USD 4.98|)
        amount = 0.0
        currency = "KHR"  # Defaulting to KHR based on standard ACLEDA format
        txn_type = "expense"

        if cash_in:
            amount = float(cash_in)
            txn_type = "income"
        elif cash_out:
            amount = float(cash_out)
            txn_type = "expense"

        # Try to extract explicit currency from description to override
        curr_match = re.search(r'\|(USD|KHR)\s+([0-9.]+)\|', desc)
        if curr_match:
            currency = curr_match.group(1)
            amount = float(curr_match.group(2))

        # Self-Transfer Detection
        user_acleda_name_upper = user_acleda_name.upper()
        desc_upper = desc.upper()
        if user_acleda_name_upper and user_acleda_name_upper in desc_upper:
            if "TRANSFERRED TO" in desc_upper or "PAYMENT FROM" in desc_upper or "PAID TO" in desc_upper:
                txn_type = "transfer"

        transactions.append({
            "date": dt,
            "amount": amount,
            "currency": currency,
            "type": txn_type,
            "description": desc,
            "bank_reference_id": f"ACL-{bank_ref}" if bank_ref else None,
            "source_bank": "ACLEDA"
        })

    return transactions