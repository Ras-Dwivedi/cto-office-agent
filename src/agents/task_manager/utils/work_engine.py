import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.db import get_collection

# =========================================================
# Collection (owned here)
# =========================================================

work_col = get_collection("work")

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
# Work Engine
# =========================================================

class WorkEngine:
    """
    Immutable engine for WORK facts.

    Responsibilities:
    - Record work done
    - Link work → event (mandatory)
    - Link work → task (optional)

    Non-responsibilities:
    - NO task creation
    - NO task mutation
    - NO load aggregation
    - NO CF logic
    """

    def record_work(
        self,
        *,
        event_id: str,
        title: str,
        started_at: datetime,
        ended_at: datetime,
        source: str,
        task_id: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        if not event_id:
            raise ValueError("event_id is mandatory for work")

        started_at = ensure_utc(started_at)
        ended_at = ensure_utc(ended_at)

        if ended_at <= started_at:
            raise ValueError("ended_at must be after started_at")

        duration_minutes = int(
            (ended_at - started_at).total_seconds() / 60
        )

        work_id = f"WORK-{uuid.uuid4().hex[:8]}"

        doc = {
            "work_id": work_id,
            "event_id": event_id,
            "task_id": task_id,          # may be None
            "title": title,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_minutes": duration_minutes,
            "source": source,            # pomodoro | manual | interrupt
            "created_at": ensure_utc(None),
            "meta": meta or {},
        }

        work_col.insert_one(doc)
        return doc

    # -----------------------------------------------------
    # Read helpers (safe, optional)
    # -----------------------------------------------------

    def get_work(self, work_id: str) -> Optional[Dict[str, Any]]:
        return work_col.find_one({"work_id": work_id}, {"_id": 0})

    def get_work_for_task(self, task_id: str):
        return list(work_col.find({"task_id": task_id}, {"_id": 0}))


# =========================================================
# Singleton
# =========================================================

work_engine = WorkEngine()
