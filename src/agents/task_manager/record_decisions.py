#!/usr/bin/env python3

import hashlib
import logging
import sys
import uuid
from datetime import datetime, timezone

from src.agents.task_manager.utils.cf_engine import process_event
from src.agents.task_manager.utils.event_engine import event_engine
from src.db import get_collection

logger = logging.getLogger("record_decision")

# =========================================================
# Collections
# =========================================================

decisions_col = get_collection("decisions")

# =========================================================
# Config
# =========================================================

QUICK_FIELDS = [
    "Decision",
    "Context",
    "Expected Outcome",
    "Review Date"
]

LONG_FIELDS = [
    "Decision",
    "Context",
    "Assumptions",
    "Expected Outcome",
    "Review Date",
    "What I Learned"
]

# =========================================================
# Helpers
# =========================================================

def utc_now():
    return datetime.now(timezone.utc)

def prompt(field: str) -> str:
    print(f"\n{field}:")
    return input("> ").strip()

def normalize(key: str) -> str:
    return key.lower().replace(" ", "_")

def context_fingerprint(*parts):
    """
    Local-only fingerprint for decision similarity / dedup.
    NOT used by CF engine.
    """
    text = "||".join(
        p.strip().lower()
        for p in parts
        if p
    )

    if not text:
        return None

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"CTX-{digest[:8].upper()}"

# =========================================================
# Main
# =========================================================

def record_decision():
    long_mode = "--long" in sys.argv
    fields = LONG_FIELDS if long_mode else QUICK_FIELDS
    mode = "LONG" if long_mode else "QUICK"

    now = utc_now()
    decision_id = f"DEC-{uuid.uuid4().hex[:8]}"

    print(f"\n📝 Recording {mode} decision\n")

    # -----------------------------------------------------
    # Canonical decision document (IMMUTABLE FACT)
    # -----------------------------------------------------
    doc = {
        "decision_id": decision_id,
        "occurred_at": now,
        "mode": mode,
        "source": "decision-cli",
        "version": 1,

        # user content
        "decision": None,
        "context": None,
        "assumptions": None,
        "expected_outcome": None,
        "review_date": None,
        "what_i_learned": None,

        # derived (local only)
        "context_fingerprint": None,
    }

    # -----------------------------------------------------
    # Collect input
    # -----------------------------------------------------
    for field in fields:
        value = prompt(field)
        if value:
            doc[normalize(field)] = value

    # Create decision event that would automatically generate CF

    event = event_engine.register_event(
        event_type="decision.made",
        occurred_at=utc_now(),
        payload={  "decision_id": decision_id,
                   "mode": mode,
                   "source": "decision-cli",
                   "decision": doc["decision"],
                   "expected_outcome": doc["expected_outcome"],
                   "review_date": doc["review_date"],
                   }
    )
    event_id = event.get("event_id")
    if event_id:
        doc["event_id"] = event.get("event_id")
        decisions_col.insert_one(doc)
    else:
        raise Exception("unble to generate event id")

    #update event if in the decisions


    # -----------------------------------------------------
    # Local fingerprint (NOT CF)
    # -----------------------------------------------------
    # doc["context_fingerprint"] = context_fingerprint(
    #     doc.get("decision"),
    #     doc.get("context"),
    #     doc.get("assumptions"),
    # )

    # -----------------------------------------------------
    # Persist decision (immutable)
    # -----------------------------------------------------
    decisions_col.insert_one(doc)

    # -----------------------------------------------------
    # Emit DECISION EVENT → CF ENGINE
    # -----------------------------------------------------

    # -----------------------------------------------------
    # Feedback
    # -----------------------------------------------------
    print("\n✅ Decision recorded successfully")
    print(f"🆔 Decision ID: {decision_id}")


# =========================================================
def main():
    record_decision()

if __name__ == "__main__":
    main()
