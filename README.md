# Receipt Reader
A receipt scanner that uses AI to read a receipt image and save the data to Google Sheets or Excel.

Runs as a **desktop app** (via pywebview) or as a **PWA on iPhone** (Add to Home Screen).

## Features
- **Upload one receipt** (PNG, JPG, WEBP, GIF, PDF) via tap/drop
- **Pattern matching** — extracts store, date, total, and items using smart regex heuristics
- **Save to Google Sheets** — auto-detects your sheet's columns and appends a new row
- **Save to Excel** — creates a new `.xlsx` file with one row of receipt data
- **Desktop executable** — builds with PyInstaller + pywebview (no browser needed)
- **iPhone PWA** — deploy to HTTPS, tap Share → "Add to Home Screen"

### How it works
**Pattern matching** — uses regex patterns to extract store name, date, total, and items from receipt text.

### Google Sheet columns
The app writes one row per receipt with these fields (auto-mapped to these existing headers):

| Timestamp | Expense/Income | Date | Month | Amount | Type of Expense | Description |
|-----------|---------------|------|-------|--------|-----------------|-------------|

## Quick Start (Download)

**Get the latest Windows executable:**
1. Go to [Releases](https://github.com/maiaqqq/receipt-reader/releases)
2. Download `ReceiptReader.exe` from the latest release
3. Create a folder with:
   - `ReceiptReader.exe`
   - `.env` (your config)
   - `service_account.json` (for Google Sheets, if using)
4. Double-click `ReceiptReader.exe` — app opens immediately!

## Development Setup

### For developers / local testing:
1. **Install Python 3.10+**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the app (dev mode):**
   ```bash
   python app.py
   ```
   Opens at [http://localhost:5000](http://localhost:5000).

## Usage
1. Upload a receipt image
2. Choose **Google Sheets** or **Excel**
3. For Sheets: paste your spreadsheet URL and link it, then choose **Add Row** or **New Excel**
4. Process Receipt 

## Build Desktop Executable

### Automated (Recommended)
Every time you create a new **git tag** (e.g., `v1.0.0`), GitHub Actions automatically:
1. Builds `ReceiptReader.exe`
2. Creates a new Release
3. Attaches the executable

```bash
# Create and push a new release tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

Then check [Releases](https://github.com/maiaqqq/receipt-reader/releases) — your `.exe` will be there in ~2 minutes!

### Manual Build (Local)
To build locally:
```bash
python generate_icons.py   # creates PWA icons (requires Pillow)
python build.py             # builds dist/ReceiptReader/ReceiptReader.exe
```

Output: `dist/ReceiptReader/ReceiptReader.exe`  
Place your `.env` and `service_account.json` next to the `.exe`.

## Google Sheets Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable the **Google Sheets API** and **Google Drive API**
3. Create a **Service Account** and download the JSON key file
4. Save it as `service_account.json` in the project root
5. Share your Google Sheet with the service account's `client_email` (Editor access)

## iPhone / PWA
1. Deploy the app to a server with HTTPS (e.g. Railway, Render)
2. Open the URL in Safari on iPhone
3. Tap **Share → Add to Home Screen**

## Requirements
- Python 3.10+
- (Optional) Google service account for Sheets integration