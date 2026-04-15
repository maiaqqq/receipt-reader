import os
import sys
import json
import base64
import re
import uuid
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file
from openai import OpenAI
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSHEETS_AVAILABLE = True
except ImportError:
    GSHEETS_AVAILABLE = False

load_dotenv()

# ── Path setup (supports PyInstaller / pywebview) ──
if getattr(sys, "frozen", False):
    _base_dir = os.path.dirname(sys.executable)
    _bundle_dir = sys._MEIPASS
else:
    _base_dir = os.path.dirname(os.path.abspath(__file__))
    _bundle_dir = _base_dir

app = Flask(
    __name__,
    template_folder=os.path.join(_bundle_dir, "templates"),
    static_folder=os.path.join(_bundle_dir, "static"),
)
app.config["UPLOAD_FOLDER"] = os.path.join(_base_dir, "uploads")
app.config["EXPORT_FOLDER"] = os.path.join(_base_dir, "exports")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["EXPORT_FOLDER"], exist_ok=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Google Sheets connection (persists while app is running)
sheets_state: dict = {"connected": False, "spreadsheet_id": None, "sheet_url": None}

SHEET_HEADERS = ["Timestamp", "Expense/Income", "Date", "Month", "Amount",
                 "Type of Expense", "Description"]


# Helpers

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# receipt parsing 
PARSE_PROMPT = """Analyze this receipt image and extract the following information as JSON.
Be as accurate as possible. If a field is not visible, use null.

Return ONLY valid JSON with this exact structure:
{
  "store_name": "Name of the store/business",
  "date": "YYYY-MM-DD format or null",
  "items": [
    {
      "name": "Item description",
      "quantity": 1,
      "price": 0.00,
      "category": "one of: Food & Groceries, Dining & Restaurants, Transportation, Healthcare, Entertainment, Shopping, Utilities, Office Supplies, Personal Care, Other"
    }
  ],
  "subtotal": 0.00,
  "tax": 0.00,
  "total": 0.00,
  "payment_method": "Cash/Credit/Debit/Other or null"
}
"""

def parse_receipt(image_path: str) -> dict:
    """Send receipt image to OpenAI Vision API and return parsed data."""
    b64 = encode_image(image_path)
    ext = image_path.rsplit(".", 1)[1].lower()
    mime = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": PARSE_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }],
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]

    return json.loads(raw)

def receipt_to_record(parsed: dict) -> dict:
    """Convert parsed receipt JSON into a flat ledger record."""
    receipt_date = parsed.get("date") or ""
    month = ""
    if receipt_date:
        try:
            month = datetime.strptime(receipt_date, "%Y-%m-%d").strftime("%B %Y")
        except ValueError:
            pass

    # Dominant category from items
    cat_totals: dict[str, float] = {}
    for item in parsed.get("items", []):
        cat = item.get("category", "Other")
        cat_totals[cat] = cat_totals.get(cat, 0) + (
            item.get("price", 0) * item.get("quantity", 1)
        )
    expense_type = max(cat_totals, key=cat_totals.get) if cat_totals else "Other"

    # Description = store + first few items
    store = parsed.get("store_name") or "Unknown Store"
    names = [i.get("name", "") for i in parsed.get("items", []) if i.get("name")]
    desc = store
    if names:
        desc += " — " + ", ".join(names[:5])
        if len(names) > 5:
            desc += f", +{len(names) - 5} more"

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "expense_income": "Expense",
        "date": receipt_date,
        "month": month,
        "amount": parsed.get("total") or 0,
        "type_of_expense": expense_type,
        "description": desc,
    }


# Google Sheets helpers
def _extract_spreadsheet_id(url: str) -> str | None:
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else None

def _get_gspread_client():
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    # Also check next to the executable
    if not os.path.isfile(creds_path):
        alt = os.path.join(_base_dir, "service_account.json")
        if os.path.isfile(alt):
            creds_path = alt
        else:
            return None
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    return gspread.authorize(creds)

def _detect_headers(ws) -> list[str]:
    """Read the first row to detect existing column headers."""
    row1 = ws.row_values(1)
    return [h.strip() for h in row1 if h.strip()]

def _ensure_headers(ws):
    """Write default headers if row 1 is empty."""
    existing = ws.row_values(1)
    if not any(cell.strip() for cell in existing):
        ws.update([SHEET_HEADERS], "A1")

def _map_record_to_row(record: dict, headers: list[str]) -> list:
    """Map a record dict to a row list matching the sheet's header order."""
    # Normalize header names for matching
    field_map = {
        "timestamp": record["timestamp"],
        "expense/income": record["expense_income"],
        "date": record["date"],
        "month": record["month"],
        "amount": record["amount"],
        "type of expense": record["type_of_expense"],
        "typeofexpense": record["type_of_expense"],
        "expense type": record["type_of_expense"],
        "category": record["type_of_expense"],
        "description": record["description"],
        "desc": record["description"],
        "notes": record["description"],
        "store": record["description"].split(" — ")[0] if " — " in record["description"] else record["description"],
    }

    row = []
    for h in headers:
        key = h.lower().strip()
        row.append(field_map.get(key, ""))
    return row

def append_to_sheets(spreadsheet_id: str, record: dict) -> list[str]:
    """Append one record to the Google Sheet. Returns the headers used."""
    gc = _get_gspread_client()
    if gc is None:
        raise RuntimeError("Service account file not found")

    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.sheet1

    headers = _detect_headers(ws)
    if not headers:
        _ensure_headers(ws)
        headers = SHEET_HEADERS

    row = _map_record_to_row(record, headers)
    ws.append_row(row, value_input_option="USER_ENTERED")
    return headers

# Excel helpers
def build_single_receipt_excel(record: dict, filepath: str):
    """Create a new Excel file with one receipt record."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Receipt"

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="7C52B8", end_color="7C52B8", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    for col, header in enumerate(SHEET_HEADERS, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    values = [
        record["timestamp"], record["expense_income"], record["date"],
        record["month"], record["amount"], record["type_of_expense"],
        record["description"],
    ]
    for col, val in enumerate(values, 1):
        cell = ws.cell(row=2, column=col, value=val)
        cell.border = thin_border
        if col == 5:
            cell.number_format = "$#,##0.00"

    for col in range(1, 8):
        ws.column_dimensions[chr(64 + col)].width = 20

    wb.save(filepath)


# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/parse", methods=["POST"])
def parse():
    """Upload one receipt image → parse it → return the record."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file or not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    filename = secure_filename(file.filename)
    unique = f"{uuid.uuid4().hex}_{filename}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique)
    file.save(filepath)

    try:
        parsed = parse_receipt(filepath)
        record = receipt_to_record(parsed)
        return jsonify({"record": record, "raw": parsed})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/submit", methods=["POST"])
def submit():
    """Take a parsed record and send it to the chosen destination."""
    data = request.get_json()
    if not data or "record" not in data:
        return jsonify({"error": "No record provided"}), 400

    record = data["record"]
    dest = data.get("destination", "sheets")  # "sheets" or "excel"
    action = data.get("action", "append")     # "append" or "new"

    if dest == "sheets" and action == "append":
        if not GSHEETS_AVAILABLE:
            return jsonify({"error": "Google Sheets libraries not installed"}), 400
        if not sheets_state["connected"]:
            return jsonify({"error": "No Google Sheet connected"}), 400
        try:
            headers = append_to_sheets(sheets_state["spreadsheet_id"], record)
            return jsonify({"message": "Row added to Google Sheets", "headers": headers})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    elif dest == "excel" or action == "new":
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"receipt_{ts}.xlsx"
        filepath = os.path.join(app.config["EXPORT_FOLDER"], filename)
        build_single_receipt_excel(record, filepath)
        return jsonify({"message": "Excel file created", "download": f"/download/{filename}"})

    return jsonify({"error": "Invalid destination/action"}), 400

@app.route("/download/<filename>")
def download(filename):
    safe = secure_filename(filename)
    filepath = os.path.join(app.config["EXPORT_FOLDER"], safe)
    if not os.path.isfile(filepath):
        return jsonify({"error": "File not found"}), 404
    return send_file(filepath, as_attachment=True, download_name=safe)

# Google Sheets connection
@app.route("/sheets/connect", methods=["POST"])
def sheets_connect():
    if not GSHEETS_AVAILABLE:
        return jsonify({"error": "Google Sheets libraries not installed. "
                        "Run: pip install gspread google-auth"}), 400

    data = request.get_json()
    url = (data or {}).get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    sid = _extract_spreadsheet_id(url)
    if not sid:
        return jsonify({"error": "Invalid Google Sheets URL"}), 400

    gc = _get_gspread_client()
    if gc is None:
        return jsonify({"error": "service_account.json not found"}), 400

    try:
        sh = gc.open_by_key(sid)
        title = sh.title
    except Exception as e:
        return jsonify({"error": f"Cannot access sheet: {e}"}), 400

    sheets_state["connected"] = True
    sheets_state["spreadsheet_id"] = sid
    sheets_state["sheet_url"] = url

    return jsonify({"title": title})

@app.route("/sheets/status")
def sheets_status():
    return jsonify(sheets_state)

@app.route("/sheets/disconnect", methods=["POST"])
def sheets_disconnect():
    sheets_state.update({"connected": False, "spreadsheet_id": None, "sheet_url": None})
    return jsonify({"message": "Disconnected"})

# PWA manifest
@app.route("/manifest.json")
def manifest():
    m = {
        "name": "Receipt Reader",
        "short_name": "Receipts",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f8f0ff",
        "theme_color": "#9b72cf",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }
    return jsonify(m)

# Entry point
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    is_exe = getattr(sys, "frozen", False)

    if is_exe:
        try:
            import webview
            webview.create_window("Receipt Reader", app, width=420, height=720)
            webview.start()
        except ImportError:
            import webbrowser, threading
            threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
            app.run(port=port)
    else:
        app.run(debug=True, port=port)
