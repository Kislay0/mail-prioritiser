# backend/fetch_unread.py
from pathlib import Path
from googleapiclient.discovery import build
from gmail_test import get_credentials

BASE_DIR = Path(__file__).resolve().parent

def fetch_unread(max_results=20):
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)
    query = "is:unread -in:trash"
    results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    messages = results.get("messages", [])
    if not messages:
        print("No unread messages found.")
        return []
    out = []
    for m in messages:
        msg = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "(no subject)")
        from_ = next((h["value"] for h in headers if h["name"].lower() == "from"), "(unknown sender)")
        snippet = msg.get("snippet", "")
        thread_id = msg.get("threadId")
        message_id = msg.get("id")
        out.append({
            "id": message_id,
            "threadId": thread_id,
            "subject": subject,
            "from": from_,
            "snippet": snippet,
        })
    print(f"Found {len(out)} unread messages (showing up to {max_results}):\n")
    for i, e in enumerate(out, 1):
        print(f"{i}. {e['subject']}")
        print(f"   From: {e['from']}")
        print(f"   id: {e['id']}  threadId: {e['threadId']}")
        print(f"   snippet: {e['snippet']}\n")
    return out

if __name__ == "__main__":
    fetch_unread()