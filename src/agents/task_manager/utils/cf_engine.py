import uuid
from datetime import datetime, timedelta
from typing import List

CF_LOOKBACK_DAYS = 7
MAX_CF_CANDIDATES = 3


# -----------------------------
# Utilities
# -----------------------------

def semantic_similarity(a: str, b: str) -> float:
    a_tokens = set(a.lower().split())
    b_tokens = set(b.lower().split())
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def cf_confidence(s_text: float, s_time: float) -> float:
    return round((0.6 * s_text) + (0.4 * s_time), 4)


# -----------------------------
# CF Hypothesis Generation
# -----------------------------

def generate_cf_hypotheses(
    event_text: str,
    contexts_col,
    now: datetime,
) -> List[dict]:

    hypotheses = []

    for cf in contexts_col.find({"status": "active"}):
        s_text = semantic_similarity(event_text, cf["title"])

        delta = (now - cf["last_activity"]).total_seconds()
        s_time = max(0.0, 1 - delta / (CF_LOOKBACK_DAYS * 86400))

        confidence = cf_confidence(s_text, s_time)

        if confidence > 0:
            hypotheses.append({
                "cf_id": cf["cf_id"],
                "confidence": confidence,
                "origin": "creation"
            })

    hypotheses.sort(key=lambda x: x["confidence"], reverse=True)
    return hypotheses[:MAX_CF_CANDIDATES]


# -----------------------------
# CF Creation (Seed Only)
# -----------------------------

def create_cf_seed(seed_text: str, contexts_col, now: datetime) -> dict:
    cf_doc = {
        "cf_id": f"CF-{uuid.uuid4().hex[:6]}",
        "title": seed_text[:80],   # seed, NOT final meaning
        "created_at": now,
        "last_activity": now,
        "status": "active",
        "version": 1
    }
    contexts_col.insert_one(cf_doc)
    return cf_doc


# -----------------------------
# Event–CF Attachment
# -----------------------------

def attach_event_to_cfs(
    event_id: str,
    event_type: str,
    cf_hypotheses: List[dict],
    edges_col,
    now: datetime
):
    for h in cf_hypotheses:
        edges_col.insert_one({
            "event_id": event_id,
            "event_type": event_type,
            "cf_id": h["cf_id"],
            "confidence": h["confidence"],
            "origin": h["origin"],
            "created_at": now,
            "last_updated": now
        })


# -----------------------------
# Public API (THIS IS WHAT ALL CALLERS USE)
# -----------------------------

def process_event_for_cf(
    event_id: str,
    event_type: str,
    event_text: str,
    contexts_col,
    edges_col,
    now: datetime,
    allow_cf_creation: bool = True
):
    """
    Single entry point for CF handling.
    """

    hypotheses = generate_cf_hypotheses(event_text, contexts_col, now)

    # If no reasonable hypotheses, create a new CF
    if not hypotheses and allow_cf_creation:
        new_cf = create_cf_seed(event_text, contexts_col, now)
        hypotheses = [{
            "cf_id": new_cf["cf_id"],
            "confidence": 1.0,
            "origin": "seed"
        }]

    attach_event_to_cfs(
        event_id=event_id,
        event_type=event_type,
        cf_hypotheses=hypotheses,
        edges_col=edges_col,
        now=now
    )

    return hypotheses
