"""
event_engine.py

Centralized event ingestion and persistence layer.

This module is responsible for:
- Creating globally unique, immutable events
- Persisting events as factual records
- Triggering downstream semantic inference (Context Fingerprinting)

Design philosophy:
------------------
- Events are *facts* (append-only, never mutated)
- Meaning (CFs, facets, pressure, tasks) is *derived* later
- This module must remain deterministic and side-effect minimal

Any logic that *interprets* events MUST live outside this engine.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from src.agents.task_manager.utils.cf_engine import process_event
from src.agents.utils.logger import logger
from src.db import get_collection

# ---------------------------------------------------------
# Database Collection
# ---------------------------------------------------------
# Stores immutable, append-only event records.
events_col = get_collection("events")


class EventEngine:
    """
    Central authority for registering all system events.

    Responsibilities (OWNS):
    ------------------------
    - Event identity generation
    - Event persistence (immutable facts)
    - Triggering semantic inference (CF linkage)

    Explicitly DOES NOT:
    -------------------
    - Create or mutate tasks
    - Create or record work
    - Apply pressure, load, or prioritization
    - Perform business logic decisions

    This separation ensures:
    - Deterministic replayability
    - Safe reprocessing when inference logic changes
    - Clear boundary between facts and meaning
    """

    def register_event(
        self,
        *,
        event_type: str,
        occurred_at: datetime,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Register a new immutable event and trigger CF inference.

        Parameters
        ----------
        event_type : str
            Canonical event type identifier
            (e.g., 'email.received', 'pomodoro.logged')

        occurred_at : datetime
            Timestamp when the event actually occurred.
            Will be normalized to UTC.

        payload : Dict[str, Any]
            Event-specific metadata.
            This is stored as-is and never mutated.

        Returns
        -------
        Dict[str, Any]
            The persisted event document.
        """

        # -----------------------------
        # Normalize time to UTC
        # -----------------------------
        # Ensures all temporal reasoning is consistent system-wide.
        occurred_at = (
            occurred_at.astimezone(timezone.utc)
            if occurred_at.tzinfo
            else occurred_at.replace(tzinfo=timezone.utc)
        )

        # -----------------------------
        # Generate stable event identity
        # -----------------------------
        # Event IDs are opaque, globally unique, and immutable.
        event_id = f"EVT-{uuid.uuid4().hex[:8]}"

        # -----------------------------
        # Persist immutable event (FACT)
        # -----------------------------
        # Once written, this document must NEVER be modified.
        doc = {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "payload": payload,
        }

        events_col.insert_one(doc)

        # -----------------------------
        # Trigger CF inference (MEANING)
        # -----------------------------
        # This step links the event to semantic context (CFs).
        # Failures here must NEVER block event persistence.
        try:
            process_event(
                event_id=event_id,
                event_type=event_type,

                # Event text extraction heuristic:
                # - title: task-like events
                # - subject: emails
                # - task_text: pomodoro sessions
                event_text=(
                    payload.get("title")
                    or payload.get("subject")     # Email
                    or payload.get("task_text")   # Pomodoro
                    or ""
                ),
                now=occurred_at,
            )
        except Exception:
            # CF inference failures are logged but non-fatal.
            # Events remain valid even if meaning extraction fails.
            logger.exception(
                "CF inference failed for event %s (%s)",
                event_id,
                event_type,
            )

        logger.debug("Event registered: %s (%s)", event_id, event_type)

        return doc


# ---------------------------------------------------------
# Singleton Instance
# ---------------------------------------------------------
# EventEngine is stateless and safe to use as a singleton.
event_engine = EventEngine()
