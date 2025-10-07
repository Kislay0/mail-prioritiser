# rules.py
import re
from typing import Dict, Any, List

# NOTE:
# PLACEMENT_SENDERS will be seeded from config.json but we include a default here.
DEFAULT_PLACEMENT_SENDERS = [
    "helpdesk.cdc@vit.ac.in",
    "vitlions2026@vitbhopal.ac.in",
]

SUPER_KEYWORDS = ["interview", "interview scheduled", "shortlist", "report by", "join", "call letter"]
URGENT_KEYWORDS = ["deadline", "apply by", "registration", "submission", "application deadline"]
MID_KEYWORDS = ["placement drive", "opportunity", "internship", "job posting", "drive details"]
TRASH_KEYWORDS = ["congratulations", "well done", "congrats", "has been placed"]

# identifiers for you
MY_IDENTIFIERS = ["Kislay", "Kislay Tiwari", "22BSA10205", "kislaytiwari2022@vitbhopal.ac.in"]

def normalize_email(addr: str) -> str:
    """Return a lowercase trimmed version of the email address (used for comparisons)."""
    if not addr:
        return ""
    return addr.strip().lower()

def extract_email_from_header(header_value: str) -> str:
    """Heuristic to extract email address from a From header value like 'Helpdesk CDC <helpdesk.cdc@vit.ac.in>'"""
    if not header_value:
        return ""
    # try to find <email@domain>
    m = re.search(r"<([^>]+)>", header_value)
    if m:
        return normalize_email(m.group(1))
    # else, maybe the value is plain email
    # split on spaces/commas and pick token with @
    tokens = re.split(r"[,\s]+", header_value)
    for t in tokens:
        if "@" in t:
            return normalize_email(t)
    return normalize_email(header_value)

def contains_date_near(text: str) -> bool:
    patterns = [
        r"\b(today|tomorrow|tonight)\b",
        r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\b"
    ]
    text_lower = (text or "").lower()
    for p in patterns:
        if re.search(p, text_lower):
            return True
    return False

def score_email(subject: str, body: str, sender_header: str, to_list: str, applied_companies: List[str]=None, placement_senders: List[str]=None, super_keywords: List[str]=None, urgent_keywords: List[str]=None, mid_keywords: List[str]=None, trash_keywords: List[str]=None) -> float:
    """
    Compute a score [0,1] for emails that are already known to be from placement-senders.
    Non-placement senders should be handled by the caller (label 'others').
    """
    score = 0.0
    text = ((subject or "") + " " + (body or "")).lower()
    sender_email = extract_email_from_header(sender_header)
    
    super_k = [k.lower() for k in (super_keywords or SUPER_KEYWORDS)]
    urgent_k = [k.lower() for k in (urgent_keywords or URGENT_KEYWORDS)]
    mid_k = [k.lower() for k in (mid_keywords or MID_KEYWORDS)]
    trash_k = [k.lower() for k in (trash_keywords or TRASH_KEYWORDS)]
    text = ((subject or "") + " " + (body or "")).lower()
    
    # sender whitelist bonus (should be placement-senders)
    if placement_senders is None:
        placement_senders = DEFAULT_PLACEMENT_SENDERS
    if any(normalize_email(ps) == sender_email for ps in placement_senders):
        score += 0.3

    # To-field directness
    if to_list and "kislaytiwari2022" in to_list.lower():
        score += 0.05

    # keyword boosts
    if any(k in text for k in super_k):
        score += 0.45
    elif any(k in text for k in urgent_k):
        score += 0.25
    elif any(k in text for k in mid_k):
        score += 0.15

    # date proximity
    if contains_date_near(text):
        score += 0.15

    # applied companies boost
    if applied_companies:
        for comp in applied_companies:
            if comp and comp.lower() in text:
                score += 0.35
                break

    # penalize clear trash (congratulatory)
    if any(k in text for k in trash_k):
        score -= 0.6

    # personalization bonus
    if any(idf.lower() in text for idf in MY_IDENTIFIERS):
        score += 0.2

    # clamp
    return max(0.0, min(1.0, score))

def classify_from_score(score: float) -> str:
    """Map score to class for placement-sender emails."""
    if score >= 0.85:
        return "super urgent"
    if score >= 0.65:
        return "urgent"
    if score >= 0.4:
        return "mid"
    if score >= 0.15:
        return "low"
    return "trash"

def explain(subject: str, body: str, sender_header: str, to_list: str, applied_companies: List[str]=None, placement_senders: List[str]=None, super_keywords: List[str]=None, urgent_keywords: List[str]=None, mid_keywords: List[str]=None, trash_keywords: List[str]=None) -> Dict[str, Any]:
    """
    Explain returns a dict with keys: score, label, reasons, sender_email, is_placement_sender.
    Caller should check is_placement_sender: if False, label will be 'others' and score will be 0.
    """
    sender_email = extract_email_from_header(sender_header)
    placement_senders_norm = [normalize_email(x) for x in (placement_senders or DEFAULT_PLACEMENT_SENDERS)]

    # robust detection:
    # - exact match against allowlist OR
    # - display-name contains placement-related keywords (like 'placement', 'placement office', 'helpdesk', 'cdc')
    sender_header_lower = (sender_header or "").lower()
    placement_keywords = ["placement", "placement office", "helpdesk", "cdc", "placementoffice"]
    is_placement = False
    if sender_email in placement_senders_norm:
        is_placement = True
    else:
        for kw in placement_keywords:
            if kw in sender_header_lower:
                is_placement = True
                break

    if not is_placement:
        return {
            "score": 0.0,
            "label": "others",
            "reasons": ["sender not in placement-senders allowlist"],
            "sender_email": sender_email,
            "is_placement_sender": False
        }

    # compute score and label
    s = score_email(subject, body, sender_header, to_list, applied_companies, placement_senders, super_keywords, urgent_keywords, mid_keywords, trash_keywords)
    label = classify_from_score(s)
    reasons: List[str] = []
    text = ((subject or "") + " " + (body or "")).lower()

    if any(normalize_email(ps) == sender_email for ps in placement_senders_norm):
        reasons.append("sender is placement cell")
    if any(k in text for k in super_keywords):
        reasons.append("super keyword found")
    elif any(k in text for k in urgent_keywords):
        reasons.append("urgent keyword found")
    elif any(k in text for k in mid_keywords):
        reasons.append("mid keyword found")
    if contains_date_near(text):
        reasons.append("date/time mentioned")
    if applied_companies:
        for c in applied_companies:
            if c and c.lower() in text:
                reasons.append(f"applied-company match: {c}")
                break
    if any(k in text for k in trash_keywords):
        reasons.append("congratulatory/trash keyword")
    if any(idf.lower() in text for idf in MY_IDENTIFIERS):
        reasons.append("personal identifier matched")

    return {
        "score": s,
        "label": label,
        "reasons": reasons,
        "sender_email": sender_email,
        "is_placement_sender": True
    }