import uuid
import logging
from datetime import datetime
from typing import List, Dict

from src.db import get_collection

# =========================================================
# Logging (local, non-intrusive)
# =========================================================

logger = logging.getLogger("cf_engine")


# =========================================================
# Configuration
# =========================================================

CF_LOOKBACK_DAYS = 7
MAX_CF_CANDIDATES = 3
CF_CREATION_THRESHOLD = 0.35


# =========================================================
# DB Collections (owned here)
# =========================================================

contexts_col = get_collection("context_fingerprints")
edges_col = get_collection("event_cf_edges")


# =========================================================
# Facet Heuristics (WEAK, SOFT, REVERSIBLE)
# =========================================================

FACET_HINTS = {
    "nature": {
        "governance": ["policy", "approval", "review", "escalation"],
        "execution": ["implement", "deploy", "fix", "configure"],
    },

    "domain": {
        "cybersecurity": ["soc", "alert", "siem", "vapt", "incident"],
        "blockchain": ["blockchain", "web3", "ledger", "smart contract"],
        "business_dev": [
            "bid", "bids", "proposal", "rfp", "eoi", "tender",
            "contract", "mou", "agreement", "funding", "grant"
        ],
    },

    "orientation": {
        "technical": [
            "config", "debug", "analyze", "code",
            "architecture", "design", "implementation"
        ],
        "business": [
            "client", "customer", "pricing", "costing",
            "proposal", "bid", "revenue", "budget",
            "commercial", "negotiation", "sla"
        ],
    },

    "action": {
        "decision": ["decide", "approve", "finalize"],
        "analysis": ["analyze", "investigate", "review"],
        "coordination": ["follow up", "meeting", "sync", "call"],
    }
}


# =========================================================
# Utilities
# =========================================================

def semantic_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_tokens = set(a.lower().split())
    b_tokens = set(b.lower().split())
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def cf_confidence(s_text: float, s_time: float, s_facet: float) -> float:
    return round(
        (0.5 * s_text) +
        (0.3 * s_time) +
        (0.2 * s_facet),
        4
    )


def extract_event_facets(event_text: str) -> Dict[str, Dict[str, float]]:
    text = (event_text or "").lower()
    facets = {}

    for facet, values in FACET_HINTS.items():
        facets[facet] = {}
        for key, keywords in values.items():
            score = sum(1 for k in keywords if k in text)
            if score > 0:
                facets[facet][key] = score

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


# =========================================================
# Safety: Event Identity Validation
# =========================================================

def _is_valid_event_id(event_id: str) -> bool:
    if not event_id:
        return False
    if "None" in str(event_id):
        return False
    return True


# =========================================================
# CF Hypothesis Generation (READ ONLY)
# =========================================================

def _generate_cf_hypotheses(event_text, now, event_facets) -> List[dict]:
    hypotheses = []

    for cf in contexts_col.find({"status": "active"}):
        try:
            s_text = semantic_similarity(event_text, cf.get("title", ""))
            delta = (now - cf.get("last_activity", now)).total_seconds()
            s_time = max(0.0, 1 - delta / (CF_LOOKBACK_DAYS * 86400))
            s_facet = facet_similarity(event_facets, cf.get("facets", {}))
            confidence = cf_confidence(s_text, s_time, s_facet)

            if confidence > 0:
                hypotheses.append({
                    "cf_id": cf["cf_id"],
                    "confidence": confidence,
                    "origin": "creation"
                })

        except Exception:
            logger.exception("CF hypothesis generation failed for cf_id=%s", cf.get("cf_id"))

    hypotheses.sort(key=lambda x: x["confidence"], reverse=True)
    return hypotheses[:MAX_CF_CANDIDATES]


# =========================================================
# CF Creation
# =========================================================

def _create_cf_seed(seed_text, now, event_facets) -> dict:
    cf_doc = {
        "cf_id": f"CF-{uuid.uuid4().hex[:6]}",
        "title": (seed_text or "")[:80],
        "created_at": now,
        "last_activity": now,
        "status": "active",
        "version": 1,
        "facets": event_facets or {},
        "stats": {
            "event_count": 0,
            "by_event_type": {}
        }
    }
    contexts_col.insert_one(cf_doc)
    return cf_doc


# =========================================================
# Persistence Helpers
# =========================================================

def _persist_event_cf_edges(event_id, event_type, hypotheses, now):
    for h in hypotheses:
        edges_col.insert_one({
            "event_id": event_id,
            "event_type": event_type,
            "cf_id": h["cf_id"],
            "confidence": h["confidence"],
            "origin": h["origin"],
            "created_at": now,
            "last_updated": now
        })


def _update_cf_activity(hypotheses, now, event_type, event_facets):
    for h in hypotheses:
        update = {
            "$set": {"last_activity": now},
            "$inc": {
                "stats.event_count": 1,
                f"stats.by_event_type.{event_type}": 1
            }
        }

        for facet, values in event_facets.items():
            for k, v in values.items():
                update["$inc"][f"facets.{facet}.{k}"] = v * h["confidence"]

        contexts_col.update_one({"cf_id": h["cf_id"]}, update)


# =========================================================
# PUBLIC API (SAFE ENTRY POINT)
# =========================================================

def process_event(
    *,
    event_id: str,
    event_type: str,
    event_text: str,
    now: datetime | None = None,
    allow_cf_creation: bool = True
) -> List[dict]:
    """
    Safe CF processing.
    - Never crashes caller
    - Never corrupts graph
    - Logs and skips invalid events
    """

    if not _is_valid_event_id(event_id):
        logger.error(
            "CF engine skipped invalid event_id='%s' event_type='%s'",
            event_id, event_type
        )
        return []

    now = now or datetime.utcnow()

    try:
        event_facets = extract_event_facets(event_text)

        hypotheses = _generate_cf_hypotheses(
            event_text=event_text,
            now=now,
            event_facets=event_facets
        )

        max_conf = max((h["confidence"] for h in hypotheses), default=0.0)

        if max_conf < CF_CREATION_THRESHOLD and allow_cf_creation:
            new_cf = _create_cf_seed(event_text, now, event_facets)
            hypotheses.append({
                "cf_id": new_cf["cf_id"],
                "confidence": 1.0,
                "origin": "seed"
            })

        _persist_event_cf_edges(event_id, event_type, hypotheses, now)
        _update_cf_activity(hypotheses, now, event_type, event_facets)

        return hypotheses

    except Exception:
        logger.exception(
            "CF engine failed for event_id='%s' event_type='%s'",
            event_id, event_type
        )
        return []
