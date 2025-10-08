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
# Allow overriding credentials path via env var if desired
CREDENTIALS_FILE = Path(os.getenv("GOOGLE_CREDENTIALS", BASE_DIR / "credentials.json"))
TOKEN_FILE = BASE_DIR / "token.json"


def get_credentials():
    creds = None
    token_path = TOKEN_FILE

    # Load existing token if it exists
    if os.path.exists(token_path):
        try:
            with open(token_path, "r") as token_file:
                token_data = json.load(token_file)
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        except Exception as e:
            print("⚠️  Token file invalid or corrupted, will regenerate:", e)
            creds = None

    # If there are no valid credentials, or they’re expired, refresh or regenerate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("🔄 Token refreshed successfully.")
            except Exception as e:
                print("⚠️  Token refresh failed, regenerating via OAuth:", e)
                creds = None

        # If we still don't have valid creds, do full OAuth flow
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=8080, prompt="consent")
            print("✅ New OAuth credentials obtained.")

        # Save the credentials for the next run
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())
            print("💾 Token saved to token.json")

    return creds


def list_labels():
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])
    print("Gmail labels found:")
    for label in labels:
        print(f"- {label['name']} (id: {label['id']})")

def message_is_unread(service, gmail_id: str) -> bool:
    """
    Returns True if message has 'UNREAD' label, False otherwise.
    Uses users().messages().get with metadata (cheap).
    """
    try:
        msg = service.users().messages().get(userId="me", id=gmail_id, format="metadata", metadataHeaders=[]).execute()
        labels = msg.get("labelIds", [])
        return "UNREAD" in labels
    except Exception as e:
        print(f"⚠️ Error checking unread status for {gmail_id}: {e}")
        # If error, default to True (safer) or False depending on preference.
        return True

if __name__ == "__main__":
    try:
        list_labels()
        print("\nSUCCESS: OAuth and Gmail API access verified. token.json created in backend/")
    except Exception as e:
        print("ERROR:", e)
        raise