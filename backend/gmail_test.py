# backend/gmail_test.py
import os
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import google.auth.exceptions

# SCOPES: readonly + modify (we request email/profile too)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
    "https://www.googleapis.com/auth/userinfo.profile",
]

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"


def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            token_data = json.load(f)
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except google.auth.exceptions.RefreshError:
                creds = None
        if not creds:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(f"Missing {CREDENTIALS_FILE}. Put OAuth client JSON there.")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=8080)
        with open(TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())
    return creds


def list_labels():
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])
    print("Gmail labels found:")
    for label in labels:
        print(f"- {label['name']} (id: {label['id']})")


if __name__ == "__main__":
    try:
        list_labels()
        print("\nSUCCESS: OAuth and Gmail API access verified. token.json created in backend/")
    except Exception as e:
        print("ERROR:", e)
        raise