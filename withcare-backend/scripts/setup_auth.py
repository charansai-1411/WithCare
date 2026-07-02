"""
Run once locally to generate token.json for Google Calendar + Drive OAuth.

Usage:
    cd withcare-backend
    python scripts/setup_auth.py

This opens a browser for Google sign-in. After consent, token.json is saved.
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
]

TOKEN_PATH = "token.json"


def find_credentials_file() -> str:
    # Accept any client_secret_*.json in current directory
    matches = glob.glob("client_secret_*.json") + glob.glob("credentials.json")
    if not matches:
        print("\nERROR: No credentials file found.")
        print("Download your OAuth 2.0 client secret from:")
        print("  GCP Console → APIs & Services → Credentials → your OAuth 2.0 Client ID → Download JSON")
        print("Place it in the withcare-backend/ directory and re-run this script.\n")
        sys.exit(1)
    return matches[0]


def main():
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing existing token...")
            creds.refresh(Request())
        else:
            creds_file = find_credentials_file()
            print(f"Using credentials file: {creds_file}")
            print("\nA browser window will open for Google sign-in.")
            print("Sign in with your Google account and grant the requested permissions.\n")

            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        print(f"\ntoken.json saved successfully!")

    print("\nPermissions granted:")
    for scope in creds.scopes or SCOPES:
        label = {
            "https://www.googleapis.com/auth/calendar.events": "Google Calendar — create/edit events",
            "https://www.googleapis.com/auth/drive.file":      "Google Drive — create/read files made by this app",
            "https://www.googleapis.com/auth/documents":       "Google Docs — create and edit documents",
        }.get(scope, scope)
        print(f"  OK  {label}")

    print("\nWithCare can now:")
    print("  - Create calendar appointments for your care plan")
    print("  - Sync events to family member calendars (with their consent)")
    print("  - Save care plans as Google Docs and share with family")


if __name__ == "__main__":
    main()
