import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from src.agents.task_manager.utils.cf_engine import process_event
from src.agents.utils.logger import logger
from src.db import get_collection

events_col = get_collection("events")


class EventEngine:
    """
    Central authority for ALL events.

    Owns:
    - event identity
    - event persistence
    - triggering CF inference

    Does NOT:
    - create tasks
    - create work
    - apply load
    """

    def register_event(
        self,
        *,
        event_type: str,
        occurred_at: datetime,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:

        # -----------------------------
        # Normalize time
        # -----------------------------
        occurred_at = (
            occurred_at.astimezone(timezone.utc)
            if occurred_at.tzinfo
            else occurred_at.replace(tzinfo=timezone.utc)
        )

        event_id = f"EVT-{uuid.uuid4().hex[:8]}"

        # -----------------------------
        # Persist immutable event
        # -----------------------------
        doc = {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "payload": payload,
        }

        events_col.insert_one(doc)

        # -----------------------------
        # CF inference (meaning layer)
        # -----------------------------
        try:
            process_event(
                event_id=event_id,
                event_type=event_type,
                event_text=payload.get("title")
                    or payload.get("subject") # Email
                    or payload.get("task_text") # Pomodoro
                    or payload.get("subject")
                    or "",
                now=occurred_at,
            )
        except Exception:
            logger.exception("CF inference failed for event %s", event_id)

        logger.debug("Event registered: %s (%s)", event_id, event_type)

        return doc


# ---------------------------------------------------------
# Singleton
# ---------------------------------------------------------

event_engine = EventEngine()
