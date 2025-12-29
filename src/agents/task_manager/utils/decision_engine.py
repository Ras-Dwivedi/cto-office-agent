import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.db import get_collection

# =========================================================
# Collection (owned here)
# =========================================================

decisions_col = get_collection("decisions")

# =========================================================
# Time helpers
# =========================================================

def ensure_utc(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# =========================================================
# Decision Engine
# =========================================================

class DecisionEngine:
    """
    Immutable engine for DECISION facts.

    Responsibilities:
    - Persist decisions
    - Link decision → event (mandatory)

    Non-responsibilities:
    - NO task creation
    - NO work creation
    - NO CF logic
    - NO load logic
    """

    def record_decision(
        self,
        *,
        event_id: str,
        decision: str,
        occurred_at: Optional[datetime] = None,
        context: Optional[str] = None,
        assumptions: Optional[str] = None,
        expected_outcome: Optional[str] = None,
        review_date: Optional[str] = None,
        source: str = "decision-cli",
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        if not event_id:
            raise ValueError("event_id is mandatory for a decision")

        occurred_at = ensure_utc(occurred_at)

        decision_id = f"DEC-{uuid.uuid4().hex[:8]}"

        doc = {
            "decision_id": decision_id,
            "event_id": event_id,          # 🔑 strong linkage
            "occurred_at": occurred_at,
            "source": source,
            "version": 1,

            # ---- decision content ----
            "decision": decision,
            "context": context,
            "assumptions": assumptions,
            "expected_outcome": expected_outcome,
            "review_date": review_date,

            # ---- metadata ----
            "meta": meta or {},
        }

        decisions_col.insert_one(doc)
        return doc

    # -----------------------------------------------------
    # Read helpers (optional)
    # -----------------------------------------------------

    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        return decisions_col.find_one({"decision_id": decision_id}, {"_id": 0})

    def get_decisions_for_event(self, event_id: str):
        return list(
            decisions_col.find({"event_id": event_id}, {"_id": 0})
        )


# =========================================================
# Singleton
# =========================================================

decision_engine = DecisionEngine()
