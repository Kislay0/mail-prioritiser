# imports needed
from supabase_client import fetch_unread_db_emails_for_user, mark_email_read
from gmail_test import get_credentials, message_is_unread
from googleapiclient.discovery import build

def sync_read_status_for_user(user_id: str):
    """
    1) Fetch DB emails with is_read = false
    2) For each, call Gmail API to check if UNREAD still present
    3) If not, mark is_read true in Supabase
    """
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)
    rows = fetch_unread_db_emails_for_user(user_id)
    updated = 0
    for row in rows:
        gid = row.get("gmail_id")
        if not gid:
            continue
        try:
            unread = message_is_unread(service, gid)
        except Exception as e:
            print("Check error for", gid, e)
            unread = True
        if not unread:
            mark_email_read(user_id, gid)
            updated += 1
    print(f"Sync read status complete. Marked {updated} emails as read.")
    return updated