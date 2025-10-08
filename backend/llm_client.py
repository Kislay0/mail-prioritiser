# llm_client.py
"""
LLM fallback client (Gemini-only). Modular so you can swap providers later.
Usage:
    from llm_client import classify_with_llm
    res = classify_with_llm(message_id, subject, snippet, max_tokens=500)
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = Path(__file__).resolve().parent / "llm_cache"
CACHE_DIR.mkdir(exist_ok=True)

# Simple schema keys we expect from the LLM
EXPECTED_KEYS = {"category", "urgency", "action_required", "deadline", "eligibility", "companies", "reason"}

# Default prompt template (few-shot minimal). Keep it short to save tokens.
PROMPT_TEMPLATE = """
You are an assistant that reads short college placement emails (subject + snippet) and returns a VALID JSON object following EXACTLY this schema (no extra keys, no explanations):

{{
  "category": "interview|job_posting|follow_up|congrats|other",
  "urgency": "super_urgent|urgent|mid|low|trash",
  "action_required": "none|reply|register|fill_form|confirm_attendance",
  "deadline": "YYYY-MM-DD or null",
  "eligibility": "all|btech|mtech|btech_final_year|others",
  "companies": ["Company A", "..."],
  "reason": "short explanation (<=20 words)"
}}

Return ONLY the JSON object (no backticks, no code fences, no commentary). Use ISO date 'YYYY-MM-DD' format or null for unknown deadlines. If a field is unknown, use null or empty list as appropriate.

Example 1
Input:
Subject: "Interview tomorrow with Acme Corp"
Body: "Interview scheduled on 2025-10-10 for BTech final-year. Reply to confirm."
Output:
{{"category":"interview","urgency":"super_urgent","action_required":"confirm_attendance","deadline":"2025-10-10","eligibility":"btech_final_year","companies":["Acme Corp"],"reason":"Interview scheduled tomorrow for BTech final-year"}}

Example 2
Input:
Subject: "Congrats — Arrise Solutions"
Body: "Congratulations to selected students. List attached."
Output:
{{"category":"congrats","urgency":"trash","action_required":"none","deadline":null,"eligibility":"all","companies":["Arrise Solutions"],"reason":"congratulatory selection announcement"}}

Now analyze this message and return ONLY the JSON:
Subject: {subject}
Body: {snippet}
"""

def _cache_path(message_id: str) -> Path:
    return CACHE_DIR / f"{message_id}.json"

def _read_cache(message_id: str) -> Optional[Dict[str, Any]]:
    p = _cache_path(message_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def _write_cache(message_id: str, data: Dict[str, Any]) -> None:
    p = _cache_path(message_id)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def validate_llm_output(obj: Dict[str, Any]) -> bool:
    if not isinstance(obj, dict):
        return False
    if not EXPECTED_KEYS.issubset(set(obj.keys())):
        return False
    # sanity checks
    if obj.get("urgency") not in {"super_urgent","urgent","mid","low","trash"}:
        return False
    if obj.get("category") not in {"interview","job_posting","follow_up","congrats","other"}:
        return False
    if obj.get("action_required") not in {"none","reply","register","fill_form","confirm_attendance"}:
        return False
    if not isinstance(obj.get("companies", []), list):
        return False
    # deadline should be either None or a string (further validation can be added)
    d = obj.get("deadline")
    if d is not None and not isinstance(d, str):
        return False
    return True

def _call_gemini(prompt: str, max_tokens: int = 300) -> str:
    """
    Call Google Gemini via google.generativeai. Expects GEMINI_API_KEY set in env.
    Uses GEMINI_MODEL env var or defaults to "gemini-2.5-flash".
    Attempts a couple of response shapes for compatibility across SDK versions.
    Returns the textual output (raw) from Gemini.
    Raises RuntimeError on fatal failure.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise RuntimeError("Gemini API key missing; set GEMINI_API_KEY in .env or environment")

    genai.configure(api_key=gemini_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Primary attempt: modern Model.generate (preferred)
    try:
        model = genai.Model(model_name)
        # Note: different SDK versions use slightly different method signatures.
        # We pass a simple generate call and handle various possible response shapes.
        resp = model.generate(prompt=prompt, max_output_tokens=max_tokens)
        # Try to extract textual content from common fields
        if hasattr(resp, "candidates") and resp.candidates:
            c = resp.candidates[0]
            if hasattr(c, "content") and c.content:
                return c.content.strip()
            if isinstance(c, dict) and "content" in c and c["content"]:
                return str(c["content"]).strip()
        if hasattr(resp, "output") and resp.output:
            return str(resp.output).strip()
        # fallback to string form
        return str(resp).strip()
    except Exception as e_primary:
        # Secondary attempt: older 'GenerativeModel' or different client shapes
        try:
            model_alt = genai.GenerativeModel(model_name)
            response = model_alt.generate_content(prompt)
            if hasattr(response, "text") and response.text:
                return response.text.strip()
            if hasattr(response, "candidates") and response.candidates:
                cand = response.candidates[0]
                if hasattr(cand, "content") and cand.content:
                    return cand.content.strip()
                if isinstance(cand, dict):
                    for k in ("content", "output", "text"):
                        if k in cand and cand[k]:
                            return str(cand[k]).strip()
            return str(response).strip()
        except Exception as e_alt:
            raise RuntimeError(f"Gemini call failed: primary error: {e_primary}; secondary error: {e_alt}")

def classify_with_llm(message_id: str, subject: str, snippet: str, max_tokens: int=500, force: bool=False) -> Optional[Dict[str, Any]]:
    """
    Returns parsed JSON dict or fallback on failure.
    Caches parsed result in llm_cache/<message_id>.json and raw responses in .raw.txt files.
    If initial parse fails, does one repair attempt asking the model to return strict JSON only.
    """
    # check parsed cache first
    if not force:
        cached = _read_cache(message_id)
        if cached:
            return cached

    prompt = PROMPT_TEMPLATE.format(subject=subject[:800], snippet=snippet[:1500])

    # first call
    try:
        raw = _call_gemini(prompt, max_tokens=max_tokens)
    except Exception as e:
        print("LLM error:", e)
        return None

    # save raw response for debugging
    try:
        _cache_path(message_id).with_suffix(".raw.txt").write_text(raw, encoding="utf-8")
    except Exception:
        pass

    # try to extract JSON object substring
    parsed = None
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_text = raw[start:end+1]
            parsed = json.loads(json_text)
    except Exception:
        parsed = None

    # if parsed but invalid schema, treat as failure
    if parsed and validate_llm_output(parsed):
        _write_cache(message_id, parsed)
        return parsed

    # SECOND-CHANCE: ask the model to return STRICT JSON only (include raw as context)
    repair_prompt = (
        "We need strictly a single JSON object ONLY (no text, no backticks). "
        "The object MUST contain the keys: category, urgency, action_required, deadline, eligibility, companies, reason. "
        "If a value is unknown, use null (for deadline) or empty list (for companies). "
        "Now produce ONLY the JSON object (no explanation). "
        "Here is the message again:\n\n"
        f"Subject: {subject}\nBody: {snippet}\n\n"
        "If the model previously returned something (shown below), please extract and return just the valid JSON per schema:\n\n"
        f"Previous model output:\n{raw}\n\n"
        "Return ONLY the JSON object now."
    )

    try:
        raw2 = _call_gemini(repair_prompt, max_tokens=min(200, max_tokens))
    except Exception as e:
        # Save second failure raw if any
        try:
            _cache_path(message_id).with_suffix(".raw2.txt").write_text(str(e), encoding="utf-8")
        except Exception:
            pass
        print("LLM error (repair call):", e)
        # fallback
        fallback = {"category":"other","urgency":"low","action_required":"none","deadline":None,"eligibility":"all","companies":[],"reason":"llm-failed-to-parse"}
        _write_cache(message_id, fallback)
        return fallback

    # save second raw
    try:
        _cache_path(message_id).with_suffix(".raw2.txt").write_text(raw2, encoding="utf-8")
    except Exception:
        pass

    # try parse raw2
    parsed2 = None
    try:
        s = raw2.find("{")
        e = raw2.rfind("}")
        if s != -1 and e != -1 and e > s:
            parsed2 = json.loads(raw2[s:e+1])
    except Exception:
        parsed2 = None

    if parsed2 and validate_llm_output(parsed2):
        _write_cache(message_id, parsed2)
        return parsed2

    # Final fallback: write original fallback but also include raw snippets in a separate debug cache
    fallback = {"category":"other","urgency":"low","action_required":"none","deadline":None,"eligibility":"all","companies":[],"reason":"llm-failed-to-parse"}
    _write_cache(message_id, fallback)
    return fallback