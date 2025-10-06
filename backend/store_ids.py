# backend/store_ids.py
import json
from pathlib import Path

STORE = Path(__file__).resolve().parent / "processed_ids.json"

def load_ids():
    if not STORE.exists():
        return set()
    with open(STORE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data)

def save_ids(id_set):
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(list(id_set), f, indent=2)
