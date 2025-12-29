import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict

from src.db import get_collection

# =========================================================
# Logging
# =========================================================

logger = logging.getLogger("cf_engine")

# =========================================================
# Configuration
# =========================================================

CF_LOOKBACK_DAYS = 7
MAX_CF_CANDIDATES = 3
CF_CREATION_THRESHOLD = 0.35

# =========================================================
# DB Collections
# =========================================================

contexts_col = get_collection("context_fingerprints")
edges_col = get_collection("event_cf_edges")

# =========================================================
# Semantic Facet Hints (MEANING ONLY)
# =========================================================

FACET_HINTS = {
    "nature": {
        "governance": ["policy", "approval", "review", "escalation", "sop"],
        "execution": ["implement", "deploy", "fix", "configure", "build"],
        "analysis": ["analyze", "investigate", "test", "evaluate"],
    },

    "domain": {
        "cybersecurity": ["soc", "alert", "siem", "vapt", "incident"],
        "blockchain": ["blockchain", "web3", "ledger", "smart contract"],
        "ops": ["infra", "server", "network", "deployment"],
        "business": [
            "proposal", "bid", "rfp", "contract", "agreement",
            "funding", "grant", "budget"
        ],
    },

    "orientation": {
        "technical": [
            "code", "architecture", "design", "implementation",
            "config", "debug"
        ],
        "managerial": [
            "review", "approve", "coordinate", "delegate",
            "follow up", "meeting"
        ],
    },

    "action": {
        "decision": ["decide", "approve", "finalize"],
        "coordination": ["meeting", "sync", "call", "follow up"],
        "delivery": ["submit", "deliver", "share", "release"],
    },
}

# =========================================================
# Time Utilities
# =========================================================

def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

# =========================================================
# Similarity Utilities
# =========================================================

def semantic_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_tokens = set(a.lower().split())
    b_tokens = set(b.lower().split())
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)

def extract_facets(text: str) -> Dict[str, Dict[str, float]]:
    text = (text or "").lower()
    facets: Dict[str, Dict[str, float]] = {}

    for facet, values in FACET_HINTS.items():
        bucket = {}
        for key, keywords in values.items():
            score = sum(1 for k in keywords if k in text)
            if score > 0:
                bucket[key] = score
        if bucket:
            facets[facet] = bucket

    return facets

def facet_similarity(event_facets, cf_facets) -> float:
    if not event_facets or not cf_facets:
        return 0.0

    score = 0.0
    weight = 0.0

    for facet, values in event_facets.items():
        for k, v in values.items():
            cf_v = cf_facets.get(facet, {}).get(k, 0.0)
            score += min(v, cf_v)
            weight += v

    return score / weight if weight else 0.0

def cf_confidence(s_text: float, s_time: float, s_facet: float) -> float:
    return round(
        0.5 * s_text +
        0.3 * s_time +
        0.2 * s_facet,
        4
    )

# =========================================================
# CF Hypothesis Generation
# =========================================================

def _generate_cf_hypotheses(
    *,
    event_text: str,
    event_time: datetime,
    event_facets: Dict[str, Dict[str, float]]
) -> List[dict]:

    hypotheses = []
    now = _to_utc(event_time)

    for cf in contexts_col.find({"status": "active"}):
        try:
            last = _to_utc(cf.get("last_activity", now))
            if not last:
                continue

            delta = (now - last).total_seconds()
            s_time = max(0.0, 1 - delta / (CF_LOOKBACK_DAYS * 86400))
            s_text = semantic_similarity(event_text, cf.get("title", ""))
            s_facet = facet_similarity(event_facets, cf.get("facets", {}))

            confidence = cf_confidence(s_text, s_time, s_facet)

            if confidence > 0:
                hypotheses.append({
                    "cf_id": cf["cf_id"],
                    "confidence": confidence,
                    "origin": "inference"
                })

        except Exception:
            logger.exception(
                "CF hypothesis failed for cf_id=%s", cf.get("cf_id")
            )

    hypotheses.sort(key=lambda x: x["confidence"], reverse=True)
    return hypotheses[:MAX_CF_CANDIDATES]

# =========================================================
# CF Creation
# =========================================================

def _create_cf_seed(title: str, when: datetime, facets: dict) -> dict:
    when = _to_utc(when)

    cf = {
        "cf_id": f"CF-{uuid.uuid4().hex[:6]}",
        "title": title[:80],
        "created_at": when,
        "last_activity": when,
        "status": "active",
        "version": 1,
        "facets": facets,
        "stats": {
            "event_count": 0,
            "by_event_type": {}
        }
    }

    contexts_col.insert_one(cf)
    return cf

# =========================================================
# Persistence
# =========================================================

def _persist_edges(event_id, event_type, hypotheses, when):
    when = _to_utc(when)

    for h in hypotheses:
        edges_col.insert_one({
            "event_id": event_id,
            "event_type": event_type,
            "cf_id": h["cf_id"],
            "confidence": h["confidence"],
            "origin": h["origin"],
            "created_at": when,
            "last_updated": when
        })

def _update_cf_stats(hypotheses, when, event_type):
    when = _to_utc(when)
    safe_event_type = event_type.replace(".", "__")

    for h in hypotheses:
        contexts_col.update_one(
            {"cf_id": h["cf_id"]},
            {
                "$set": {"last_activity": when},
                "$inc": {
                    "stats.event_count": 1,
                    f"stats.by_event_type.{safe_event_type}": 1
                }
            }
        )


# =========================================================
# PUBLIC API
# =========================================================

def process_event(
    *,
    event_id: str,
    event_type: str,
    event_text: str,
    now: datetime | None = None,
    allow_cf_creation: bool = True
) -> List[dict]:

    if not event_id:
        logger.error("Invalid event_id for CF processing")
        return []

    now = _to_utc(now or datetime.utcnow())

    try:
        facets = extract_facets(event_text)

        hypotheses = _generate_cf_hypotheses(
            event_text=event_text,
            event_time=now,
            event_facets=facets
        )

        max_conf = max((h["confidence"] for h in hypotheses), default=0.0)

        if max_conf < CF_CREATION_THRESHOLD and allow_cf_creation:
            cf = _create_cf_seed(event_text, now, facets)
            hypotheses.append({
                "cf_id": cf["cf_id"],
                "confidence": 1.0,
                "origin": "seed"
            })

        _persist_edges(event_id, event_type, hypotheses, now)
        _update_cf_stats(hypotheses, now, event_type)

        return hypotheses

    except Exception:
        logger.exception(
            "CF engine failed for event_id=%s event_type=%s",
            event_id, event_type
        )
        return []
