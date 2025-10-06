# backend/process_and_classify.py
import json
from pathlib import Path
from datetime import datetime

from fetch_unread import fetch_unread
from rules import explain
from store_ids import load_ids, save_ids

BASE = Path(__file__).resolve().parent
PROCESSED_FILE = BASE / "processed_ids.json"
OUT_FILE = BASE / "classified_emails.json"
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

def persist_classified(record):
    records = []
    if OUT_FILE.exists():
        try:
            with open(OUT_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []
    records.insert(0, record)  # newest first
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)

def main():
    cfg = load_config()
    placement_senders = cfg.get("placement_senders", [])
    applied_companies = cfg.get("applied_companies", [])
    processed = load_ids()
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

        explanation = explain(subject, snippet, sender, to_list, applied_companies, placement_senders)
        label = explanation["label"]
        score = explanation["score"]
        reasons = explanation.get("reasons", [])
        sender_email = explanation.get("sender_email", "")

        rec = {
            "id": mid,
            "threadId": m.get("threadId"),
            "received_at": datetime.utcnow().isoformat() + "Z",
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

        # Persist record and mark processed
        persist_classified(rec)
        newly_processed.add(mid)

    # merge and save processed ids
    if newly_processed:
        processed.update(newly_processed)
        save_ids(processed)
        print(f"Processed and saved {len(newly_processed)} messages.")
    else:
        print("No new messages were processed.")

if __name__ == "__main__":
    main()