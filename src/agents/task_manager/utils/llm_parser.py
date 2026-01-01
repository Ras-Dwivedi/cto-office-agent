"""
LLM COERCERS & NORMALIZERS

Purpose
-------
This module provides a hardened, production-grade pipeline to safely handle
LLM-generated "JSON-ish" outputs for TASK and DECISION extraction.

Design Principles
-----------------
- LLM output is UNTRUSTED input
- Accept many formats, emit ONE canonical format
- Never raise on malformed content (except at parse boundary)
- Drop invalid ontology objects intentionally
- No DB writes, no side effects

Pipeline
--------
LLM text
  → normalize_llm_json()
  → parse_llm_json_array()
  → coerce_*_array()
  → SAFE structured objects
"""

import ast
import json
import re
from datetime import datetime

from src.agents.utils.logger import logger

# =========================================================
# INVALID PLACEHOLDER VALUES (ONTOLOGY GUARDS)
# =========================================================

INVALID_TASK_TITLES = {
    "no task",
    "no tasks",
    "not applicable",
    "n/a",
    "none",
    "null",
}

INVALID_DECISION_PHRASES = {
    "no decision",
    "no decision found",
    "not applicable",
    "n/a",
    "none",
    "null",
    "nil",
}


# =========================================================
# MONTH MAP (TEXTUAL DATE SUPPORT)
# =========================================================

MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


# =========================================================
# LLM JSON NORMALIZATION & PARSING
# =========================================================
def extract_list_from_text(text: str) -> list[str]:
    """
    Extract the first balanced Python/JSON list from a text blob
    and return it as a list of STRINGIFIED JSON objects.

    - Ignores prose and markdown
    - Does NOT parse or validate JSON
    - Returns list[str], where each element is a `{...}` string
    - Returns [] if no list exists
    """

    if not text or not isinstance(text, str):
        return []

    # --------------------------------------------------
    # 1. Strip markdown fences
    # --------------------------------------------------
    cleaned = re.sub(r"```[\w]*", "", text, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "").strip()

    # --------------------------------------------------
    # 2. Extract first balanced [...]
    # --------------------------------------------------
    start = cleaned.find("[")
    if start == -1:
        return []

    depth = 0
    end = None

    for i in range(start, len(cleaned)):
        if cleaned[i] == "[":
            depth += 1
        elif cleaned[i] == "]":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end is None:
        return []

    list_body = cleaned[start + 1 : end].strip()
    if not list_body:
        return []

    # --------------------------------------------------
    # 3. Split top-level `{...}` objects
    # --------------------------------------------------
    items = []
    buf = []
    brace_depth = 0

    for ch in list_body:
        if ch == "{":
            brace_depth += 1
        if brace_depth > 0:
            buf.append(ch)
        if ch == "}":
            brace_depth -= 1
            if brace_depth == 0:
                item = "".join(buf).strip()
                if item:
                    items.append(item)
                buf = []

    return items

def normalize_llm_json(text: str) -> dict:
    """
    Normalize LLM 'JSON-ish' output into a valid JSON object.

    Handles:
    - Stringified JSON
    - Python literals (None, True, False)
    - Minor formatting noise

    Returns:
    - dict if valid
    - {} if invalid
    Never raises.
    """

    if not text or not isinstance(text, str):
        return {}

    t = text.strip()

    # ---------------------------------------------
    # 1. Remove enclosing quotes if stringified JSON
    # ---------------------------------------------
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        t = t[1:-1].strip()

    # ---------------------------------------------
    # 2. Normalize Python literals → JSON literals
    # ---------------------------------------------
    replacements = {
        r"\bNone\b": "null",
        r"\bTrue\b": "true",
        r"\bFalse\b": "false",
    }

    for pattern, repl in replacements.items():
        t = re.sub(pattern, repl, t)

    # ---------------------------------------------
    # 3. Parse JSON safely
    # ---------------------------------------------
    try:
        obj = json.loads(t)
    except Exception:
        try:
            # Fallback: Python literal (single quotes, etc.)
            obj = ast.literal_eval(t)
        except Exception:
            return {}

    # ---------------------------------------------
    # 4. Ensure object is a dict
    # ---------------------------------------------
    if not isinstance(obj, dict):
        return {}

    return obj

# =========================================================
# SHARED COERCERS (PRIMITIVES)
# =========================================================

def coerce_bool(value, default=None):
    """
    Coerce various truthy/falsey representations to bool.

    Returns:
    - True / False if confidently inferred
    - default otherwise
    """

    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        v = value.lower().strip()
        if v in {"true", "yes", "y"}:
            return True
        if v in {"false", "no", "n"}:
            return False

    return default





def coerce_date(value):
    """
    Accept multiple date formats and normalize to YYYY-MM-DD.

    Supported:
    - YYYY-MM-DD
    - DD/MM/YY, DD/MM/YYYY
    - DD-MM-YYYY
    - 26th December 2025
    - 26 Dec 2025

    Returns None if invalid or ambiguous.
    Never raises.
    """

    if not value:
        return None

    v = str(value).strip().lower()

    if v in {"null", "none", "n/a"}:
        return None

    # ISO format
    try:
        return datetime.strptime(v, "%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        pass

    # Indian numeric formats
    m = re.match(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$", v)
    if m:
        d, mth, y = map(int, m.groups())
        if y < 100:
            y += 2000
        try:
            return datetime(y, mth, d).strftime("%Y-%m-%d")
        except Exception:
            return None

    # Textual: 26th December 2025
    m = re.match(r"(\d{1,2})(st|nd|rd|th)?\s+([a-z]+),?\s+(\d{4})", v)
    if m:
        d, _, month_str, y = m.groups()
        month = MONTHS.get(month_str)
        if month:
            try:
                return datetime(int(y), month, int(d)).strftime("%Y-%m-%d")
            except Exception:
                return None

    # Short textual: 26 Dec 2025
    m = re.match(r"(\d{1,2})\s+([a-z]{3,9})\s+(\d{4})", v)
    if m:
        d, month_str, y = m.groups()
        month = MONTHS.get(month_str)
        if month:
            try:
                return datetime(int(y), month, int(d)).strftime("%Y-%m-%d")
            except Exception:
                return None

    return None


# =========================================================
# DECISION COERCERS
# =========================================================

def coerce_confidence(value):
    """
    Normalize confidence to {high, medium, low}.
    Defaults to 'low'.
    """

    if not value:
        return "low"

    v = str(value).lower().strip()
    return v if v in {"high", "medium", "low"} else "low"


def coerce_decision_object(d: dict) -> dict | None:
    """
    Coerce a single decision object into canonical form.

    Returns None if:
    - Not a dict
    - Missing decision text
    - Decision is a placeholder / non-decision
    """

    if not isinstance(d, dict):
        return None

    decision_raw = d.get("decision")
    if not decision_raw:
        return None

    decision_text = str(decision_raw).strip()
    if not decision_text:
        return None

    lowered = decision_text.lower()
    if any(p in lowered for p in INVALID_DECISION_PHRASES):
        return None

    return {
        "decision": decision_text,
        "context": (
            str(d.get("context")).strip()
            if d.get("context") not in {None, "null", "None"}
            else None
        ),
        "confidence": coerce_confidence(d.get("confidence")),
        "reversible": coerce_bool(d.get("reversible")),
        "effective_date": coerce_date(d.get("effective_date")),
    }


def coerce_decision_array(raw_decisions:list) -> list[dict]:
    """
    Coerce a list of raw decision objects into a safe decision list.
    """
    if not raw_decisions or not isinstance(raw_decisions, list):
        logger.debug("coerce_decision_array returned an empty list or is not a list")
        return []

    clean = []
    for d in raw_decisions:
        coerced = coerce_decision_object(d)
        if coerced:
            clean.append(coerced)
        else:
            logger.debug(f"coerce_decision_array failed to coerce {d}")
    return clean


# =========================================================
# TASK COERCERS
# =========================================================

def coerce_task_title(value):
    """
    Validate and clean task title.
    """

    if not value:
        return None

    title = str(value).strip()
    if not title:
        return None

    lowered = title.lower()
    if any(p in lowered for p in INVALID_TASK_TITLES):
        return None

    return title


def coerce_owner(value):
    """
    Normalize owner field.
    """

    if not value:
        return None

    owner = str(value).strip()
    return None if owner.lower() in {"none", "null", "n/a"} else owner


def coerce_task_object(t: dict) -> dict | None:
    """
    Coerce a single task object into canonical form.
    """

    if not isinstance(t, dict):
        return None

    title = coerce_task_title(t.get("title"))
    if not title:
        return None

    return {
        "title": title,
        "owner": coerce_owner(t.get("owner")),
        "due_by": coerce_date(t.get("due_by")),
        "institutional": coerce_bool(t.get("institutional"), default=False),
        "blocks_others": coerce_bool(t.get("blocks_others"), default=False),
        "external_dependency": coerce_bool(t.get("external_dependency"), default=False),
        "delegatable": coerce_bool(t.get("delegatable"), default=True),
    }


def coerce_task_array(raw_tasks: list) -> list[dict]:
    """
    Coerce a list of raw task objects into a safe task list.
    """

    if not raw_tasks or not isinstance(raw_tasks, list):
        return []

    clean = []
    for t in raw_tasks:
        coerced = coerce_task_object(t)
        if coerced:
            clean.append(coerced)

    return clean


def _parse_from_llm(llm_txt, *, coercer):
    items = extract_list_from_text(llm_txt)
    if not items:
        return []

    normalized = []
    for e in items:
        obj = normalize_llm_json(e)
        if obj:
            normalized.append(obj)

    return coercer(normalized) if normalized else []

def get_decision_from_llm_str(llm_txt):
    """
    Extract, normalize, and coerce DECISION objects from raw LLM text.

    Returns:
    - list[dict] of valid decision objects
    - [] if none found or all invalid
    Never raises.
    """
    return _parse_from_llm(llm_txt, coercer=coerce_decision_array)

def get_task_from_llm_str(llm_txt):
    """
    Extract, normalize, and coerce TASK objects from raw LLM text.

    Returns:
    - list[dict] of valid task objects
    - [] if none found or all invalid
    Never raises.
    """
    return _parse_from_llm(llm_txt, coercer=coerce_task_array)





def main():
    LLM_DECISION_TEXT = """
    [
      {
        "decision": "Approved the decryption of the response",
        "context": "The CTO was able to decrypt the response correctly.",
        "confidence": "high",
        "reversible": false,
        "effective_date": "2023-09-11"
      }
    ]
    """
    print (get_decision_from_llm_str(LLM_DECISION_TEXT))
#
    LLM_TASK_TEXT_VALID = """  [
  {
    "title": "Review Mohd Sahil's Casual Leave Application",
    "owner": "Ras Dwivedi",
    "due_by": null,
    "institutional": true,
    "blocks_others": false,
    "external_dependency": false,
    "delegatable": false
  }
] """
    print (get_task_from_llm_str(LLM_TASK_TEXT_VALID))


if __name__ == "__main__":
    main()