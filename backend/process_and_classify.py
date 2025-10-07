# backend/process_and_classify.py
import json
from pathlib import Path
from datetime import datetime, timezone

import os
from dotenv import load_dotenv
load_dotenv()

# Supabase helper functions
from supabase_client import insert_email_record, fetch_processed_ids, fetch_companies_for_user, fetch_keywords_for_user

from fetch_unread import fetch_unread
from rules import explain
from llm_client import classify_with_llm

BASE = Path(__file__).resolve().parent
CONFIG_FILE = BASE / "config.json"

def load_config():
    if not CONFIG_FILE.exists():
        # default config; edit config.json later
        default = {
            "placement_senders": ["helpdesk.cdc@vit.ac.in", "vitlions2026@vitbhopal.ac.in"],
            "applied_companies": ["Devrev", "Solarwinds", "7-Eleven", "Nvidia", "PTC India", "UI Path", "Arrise Solutions"],
            "thresholds": {"super": 0.85, "urgent": 0.65, "mid": 0.4, "low": 0.15},
            "profile": {"degree": "BTech", "identifiers": ["Kislay", "Kislay Tiwari", "22BSA10205", "kislaytiwari2022@vitbhopal.ac.in"]},
            "attachment_handling": "flag",
            "digest_time": "21:30"
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2)
        return default
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    cfg = load_config()
    # load dynamic lists from Supabase (fallback to config if empty)
    USER_ID = os.getenv("SUPABASE_USER_ID")
    if not USER_ID:
        raise RuntimeError("SUPABASE_USER_ID not set in .env")

    placement_senders = cfg.get("placement_senders", [])
    # fetch companies and keywords from supabase
    applied_companies = fetch_companies_for_user(USER_ID) or cfg.get("applied_companies", [])
    keyword_rows = fetch_keywords_for_user(USER_ID) or []
    # build keyword lists for the rules engine
    # We'll map keywords into categories: super, urgent, mid, trash, default -> low
    SUPER_KEYWORDS = [r["keyword"] for r in keyword_rows if r.get("type") == "super"]
    URGENT_KEYWORDS = [r["keyword"] for r in keyword_rows if r.get("type") == "urgent"]
    MID_KEYWORDS = [r["keyword"] for r in keyword_rows if r.get("type") == "mid"]
    TRASH_KEYWORDS = [r["keyword"] for r in keyword_rows if r.get("type") == "trash"]
    # fallback: if any empty, keep from config defaults in rules (rules.py has defaults)
    # fetch already-processed gmail_ids from Supabase for this user (avoid reprocessing)
    processed_list = fetch_processed_ids(USER_ID)
    processed = set(processed_list or [])
    # print("Loaded config:", CONFIG_FILE)
    msgs = fetch_unread(max_results=50)
    if not msgs:
        print("No messages to process.")
        return

    newly_processed = set()
    for m in msgs:
        mid = m["id"]
        if mid in processed:
            print(f"Skipping (already processed): {mid} - {m.get('subject')}")
            continue
        subject = m.get("subject", "")
        snippet = m.get("snippet", "")
        sender = m.get("from", "")
        to_list = ""  # placeholder; can be improved later

        explanation = explain(
            subject, snippet, sender, to_list,
            applied_companies,
            placement_senders,
            super_keywords=SUPER_KEYWORDS,
            urgent_keywords=URGENT_KEYWORDS,
            mid_keywords=MID_KEYWORDS,
            trash_keywords=TRASH_KEYWORDS
        )
        label = explanation["label"]
        score = explanation["score"]
        reasons = explanation.get("reasons", [])
        sender_email = explanation.get("sender_email", "")
        
        if explanation.get("is_placement_sender") and 0.45<=score<=0.85:
            llm_res = classify_with_llm(mid, subject, snippet, max_tokens=500)
            if llm_res:
                llm_urgency = llm_res.get("urgency")
                severity_order = {"super_urgent":4, "urgent":3, "mid":2, "low":1, "trash":0}
                if llm_urgency in severity_order and severity_order.get(llm_urgency,0) > severity_order.get(label,0):
                    label = llm_urgency
                    reasons.append("llm_override: "+ (llm_res.get("reason") or ""))
                else:
                    reasons.append("llm_supplement: "+ (llm_res.get("reason") or ""))

        rec = {
            "id": mid,
            "threadId": m.get("threadId"),
            "received_at": datetime.now(timezone.utc).isoformat() + "Z",
            "subject": subject,
            "from": sender,
            "sender_email": sender_email,
            "snippet": snippet,
            "label": label,
            "score": score,
            "reasons": reasons
        }

        # Print summary to console (human-friendly)
        print("------------------------------------------------------------")
        print(f"Subject: {subject}")
        print(f"From: {sender}")
        print(f"Label: {label} (score={score:.2f})")
        print("Reasons:", "; ".join(reasons) if reasons else "none")
        print(f"Message ID: {mid}")
        print("------------------------------------------------------------\n")

        # Persist to Supabase
        # Build DB-ready payload (column names match the emails table)
        db_record = {
            "user_id": USER_ID,
            "gmail_id": mid,
            "thread_id": m.get("threadId"),
            "from_address": sender,
            "subject": subject,
            "snippet": snippet,
            "category": label,
            "score": score,
            "reasons": reasons,
            "llm_used": bool('llm_res' in locals() and llm_res),
            # store llm result as JSON/string for audit; the supabase client will accept dicts
            "llm_notes": llm_res if ('llm_res' in locals() and isinstance(llm_res, dict)) else None,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

        resp = insert_email_record(db_record)
        # if insert succeeded, mark as processed locally (so we don't re-attempt same insert this run)
        newly_processed.add(mid)

    # We already inserted new records into Supabase; just report how many
    if newly_processed:
        print(f"Processed and saved {len(newly_processed)} messages to Supabase.")
    else:
        print("No new messages were processed.")

if __name__ == "__main__":
    main()