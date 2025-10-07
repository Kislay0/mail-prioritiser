from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def insert_email_record(data: dict):
    """Insert a single email classification record."""
    try:
        response = supabase.table("emails").insert(data).execute()
        print(f"✅ Saved email {data.get('subject', '')[:30]}... to Supabase.")
        return response
    except Exception as e:
        print(f"⚠️  Failed to insert into Supabase: {e}")
        return None

def fetch_processed_ids(user_id: str):
    """Return list of Gmail IDs already processed."""
    try:
        response = supabase.table("emails").select("gmail_id").eq("user_id", user_id).execute()
        return [r["gmail_id"] for r in response.data]
    except Exception as e:
        print(f"⚠️  Error fetching processed IDs: {e}")
        return []

def clear_emails_for_user(user_id: str):
    """Delete all stored emails (for testing)."""
    supabase.table("emails").delete().eq("user_id", user_id).execute()
    print("🧹 Cleared emails for user.")
    
# === dynamic companies / keywords helpers ===
def fetch_companies_for_user(user_id: str):
    """Return list of company names (strings) for the user."""
    try:
        resp = supabase.table("companies").select("name").eq("user_id", user_id).execute()
        return [r["name"] for r in (resp.data or [])]
    except Exception as e:
        print("⚠️ fetch_companies_for_user error:", e)
        return []

def fetch_keywords_for_user(user_id: str):
    """Return list of keyword dicts for the user: [{'keyword':k, 'weight':w, 'type':t}, ...]"""
    try:
        resp = supabase.table("keywords").select("keyword,weight,type").eq("user_id", user_id).execute()
        return resp.data or []
    except Exception as e:
        print("⚠️ fetch_keywords_for_user error:", e)
        return []

def add_company(user_id: str, name: str):
    try:
        resp = supabase.table("companies").insert({"user_id": user_id, "name": name}).execute()
        print(f"✅ Added company: {name}")
        return resp
    except Exception as e:
        print("⚠️ add_company failed:", e)
        return None

def delete_company(user_id: str, name: str):
    try:
        resp = supabase.table("companies").delete().eq("user_id", user_id).eq("name", name).execute()
        print(f"🗑️ Deleted company: {name}")
        return resp
    except Exception as e:
        print("⚠️ delete_company failed:", e)
        return None

def add_keyword(user_id: str, keyword: str, weight: float = 1.0, ktype: str = "general"):
    try:
        resp = supabase.table("keywords").insert({"user_id": user_id, "keyword": keyword, "weight": weight, "type": ktype}).execute()
        print(f"✅ Added keyword: {keyword}")
        return resp
    except Exception as e:
        print("⚠️ add_keyword failed:", e)
        return None

def delete_keyword(user_id: str, keyword: str):
    try:
        resp = supabase.table("keywords").delete().eq("user_id", user_id).eq("keyword", keyword).execute()
        print(f"🗑️ Deleted keyword: {keyword}")
        return resp
    except Exception as e:
        print("⚠️ delete_keyword failed:", e)
        return None