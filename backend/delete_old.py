# delete_old.py
from dotenv import load_dotenv
load_dotenv()
import os
from supabase_client import delete_emails_older_than

USER_ID = os.getenv("SUPABASE_USER_ID")
if not USER_ID:
    raise RuntimeError("SUPABASE_USER_ID not set in .env")
delete_emails_older_than(USER_ID, 2)