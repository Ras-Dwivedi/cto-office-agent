import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from src.db import get_collection
from src.agents.task_manager.utils.task_engine import task_engine

logger = logging.getLogger("event_engine")

events_col = get_collection("events")


class EventEngine:
    """
    Central authority for ALL events.
    Owns:
    - event identity
    - task creation (when applicable)
    - event → task linkage
    """

    def register_event(
        self,
        *,
        event_type: str,
        occurred_at: datetime,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:

        occurred_at = (
            occurred_at.astimezone(timezone.utc)
            if occurred_at.tzinfo
            else occurred_at.replace(tzinfo=timezone.utc)
        )

        event_id = f"EVT-{uuid.uuid4().hex[:8]}"

        # -------------------------------------------------
        # TASK CREATION RULES (CRITICAL)
        # -------------------------------------------------
        task_id = None

        if event_type in {
            "task.created",
            "interrupt.logged",
            "email.task",
            "decision.task",
        }:
            task = task_engine.create_task(
                title=payload.get("title"),
                source=payload.get("source", event_type),
                source_ref=event_id,
                created_at=occurred_at,
                extra=payload,
            )
            task_id = task["task_id"]

        # -------------------------------------------------
        # Persist event
        # -------------------------------------------------
        doc = {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "task_id": task_id,
            "payload": payload,
        }

        events_col.insert_one(doc)

        return doc


# ---------------------------------------------------------
# Singleton
# ---------------------------------------------------------

event_engine = EventEngine()
