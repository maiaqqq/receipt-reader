"""
Build Receipt Reader into a standalone desktop executable.
Uses pywebview for a native window (no browser needed).
Usage:
    pip install pyinstaller pywebview
    python build.py
Output: dist/ReceiptReader/ReceiptReader.exe
"""

import subprocess
import sys

def main():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "ReceiptReader",
        "--noconfirm",
        "--clean",
        # Bundle templates & static as data files
        "--add-data", "templates;templates",
        "--add-data", "static;static",
        # Hidden imports
        "--hidden-import", "gspread",
        "--hidden-import", "google.auth",
        "--hidden-import", "google.oauth2",
        "--hidden-import", "google.oauth2.service_account",
        "--hidden-import", "openpyxl",
        "--hidden-import", "dotenv",
        "--hidden-import", "webview",
        "--hidden-import", "clr",            # pywebview Windows dependency
        "--hidden-import", "pythonnet",
        # No console window
        "--windowed",
        # Entry point
        "app.py",
    ]

    print("Building ReceiptReader.exe ...")
    print(f"  Command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("\nBuild complete!  ->  dist/ReceiptReader/ReceiptReader.exe")
        print("Place your .env and service_account.json next to ReceiptReader.exe.")
    else:
        print("\nBuild failed.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
