# src/context_fingerprint.py

import uuid
from datetime import datetime

CONFIDENCE_THRESHOLD = 0.75
CF_LOOKBACK_DAYS = 7


def semantic_similarity(a: str, b: str) -> float:
    a_tokens = set(a.lower().split())
    b_tokens = set(b.lower().split())
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def cf_confidence(s_text: float, s_time: float) -> float:
    """
    Lightweight confidence formula.
    Expand later with actors/artifacts.
    """
    return (0.7 * s_text) + (0.3 * s_time)


def find_or_create_cf(task_text, contexts_col, now: datetime):
    best_cf = None
    best_score = 0.0

    for cf in contexts_col.find({"status": "active"}):
        s_text = semantic_similarity(task_text, cf["title"])

        delta_seconds = (now - cf["last_activity"]).total_seconds()
        s_time = max(0.0, 1 - delta_seconds / (CF_LOOKBACK_DAYS * 86400))

        score = cf_confidence(s_text, s_time)

        if score > best_score:
            best_score = score
            best_cf = cf

    if best_cf and best_score >= CONFIDENCE_THRESHOLD:
        return best_cf

    # Create new CF
    cf_doc = {
        "cf_id": f"CF-{uuid.uuid4().hex[:6]}",
        "title": task_text,
        "created_at": now,
        "last_activity": now,
        "total_pomodoros": 0,
        "total_time_minutes": 0,
        "status": "active"
    }
    contexts_col.insert_one(cf_doc)
    return cf_doc
