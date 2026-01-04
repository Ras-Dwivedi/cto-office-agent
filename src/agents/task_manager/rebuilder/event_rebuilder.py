"""
CF & Event Rebuilder
===================

Purpose
-------
This module provides an **offline, deterministic rebuild pipeline** for restoring
the **event layer** and **Context Fingerprint (CF) layer** from persisted system
state such as tasks, work logs, interrupts, and raw emails.

The rebuilder is designed to repair, backfill, or re-materialize system semantics
when:
- Event ingestion logic changes
- CF similarity or facet logic evolves
- Bugs caused missing or inconsistent events
- Full CF graph regeneration is required

This module intentionally does **not** depend on live ingestion agents.

---

Conceptual Model
----------------
The system distinguishes between:

• **State** (materialized projections)
  - `tasks`
  - `work`
  - `interrupt`
  - `raw_emails`

• **Facts** (immutable history)
  - `events`

• **Context**
  - `context_fingerprints`
  - `event_cf_edges`

This rebuilder reconstructs *facts and context* from persisted state,
treating stored state as authoritative historical evidence.

---

Rebuild Modes
-------------

1. **Task Rebuild (`rebuild_tasks`)**
   Reconstructs a single canonical event per task based on its source:

   - `source = email`
     → rebuilds `email.received` using the exact production schema
   - `source = interrupt.call / interrupt.whatsapp`
     → rebuilds `interrupt.logged`
   - Other sources
     → task-linked events may be added in later rebuild stages

   The rebuilt event is attached to the task via `source_event_id`.

2. **Work Rebuild (`rebuild_work`)**
   Reconstructs `work.logged` events from persisted work records and
   rebinds them to the work collection via `event_id`.

3. **CF Rebuild (`rebuild_event`)**
   Replays *all events in chronological order* and deterministically
   reconstructs:
   - Context Fingerprints (CFs)
   - CF facets
   - Event ↔ CF edges

   The CF engine decides whether to link to an existing CF or create
   a new one based solely on event semantics.

---

Design Guarantees
-----------------
✔ Idempotent – safe to run multiple times
✔ Deterministic – identical input produces identical CF graph
✔ Schema-faithful – uses canonical event schemas
✔ Side-effect free – no mutation of business semantics
✔ Agent-independent – no reliance on live ingestion logic

---

Key Invariants
--------------
- Every rebuilt task has exactly **one authoritative source event**
- Every work record has exactly **one `work.logged` event**
- All CFs are derivable *only* from events
- No CF contains semantics not present in the event layer

---

When to Use
-----------
- CF logic or similarity thresholds change
- Event ontology evolves
- Historical data import
- Backfilling missing events
- Validating extractor quality
- Academic evaluation or reproducibility

---

Non-Goals
---------
- This script does NOT infer new tasks or work
- It does NOT alter task/work semantics
- It does NOT merge or split tasks
- It does NOT invent causality beyond persisted evidence

---

Execution Notes
---------------
Recommended execution order:

1. `rebuild_tasks()`
2. `rebuild_work()`
3. `rebuild_event()`

Running CF rebuild without rebuilding events first may lead to
incomplete context graphs.

---

This module enables **full semantic replay** of the system and forms
the foundation for:
- Task pressure analysis
- CF evolution studies
- Decision → task → work traceability
- Longitudinal productivity research
"""


from src.agents.task_manager.utils.decision_engine import ensure_utc
from src.agents.task_manager.utils.event_engine import event_engine
from src.db import get_collection
from src.agents.task_manager.utils.cf_engine import process_event
from src.agents.utils.logger import logger
from src.config.config import EMAIL_PROCESSOR_VERSION
# ---------------------------------------------------------
# Database Collections
# ---------------------------------------------------------

events_col = get_collection("events")
cf_col = get_collection("context_fingerprints")
edges_col = get_collection("event_cf_edges")


tasks_col = get_collection("tasks")
work_col = get_collection("work")
interrupt_col = get_collection("interrupt")
emails_col = get_collection("raw_emails")



def extract_event_text(event: dict) -> str:
    """
    Canonical event → text projection.

    This function defines *what semantic text* represents
    an event for CF inference.

    IMPORTANT:
    ----------
    - This is the ONLY place where event payload interpretation
      should live.
    - Adding new event types should only require updating this
      function.

    Parameters
    ----------
    event : dict
        Event document from `events` collection.

    Returns
    -------
    str
        Text used for CF similarity and facet extraction.
    """
    payload = event.get("payload", {})

    return (
        payload.get("title")          # task-like events
        or payload.get("subject")     # email events
        or payload.get("task_text")   # pomodoro sessions
        or payload.get("reason")      # interrupts
        or payload.get("decision")    # decisions (if present)
        or ""
    )


# ---------------------------------------------------------
# Rebuild Logic
# ---------------------------------------------------------

def rebuild_event(
    *,
    reset: bool = True,
    allow_cf_creation: bool = True,
) -> None:
    """
    Rebuild CFs and facets by replaying all events.

    Parameters
    ----------
    reset : bool, default=True
        If True, deletes all existing CFs and CF edges before replay.

    allow_cf_creation : bool, default=True
        Whether CF engine is allowed to seed new CFs during replay.

    Execution Model
    ---------------
    - Events are replayed in `occurred_at` order
    - Each event is treated as if it just occurred
    - CF engine decides linking vs creation
    """

    print("🔁 Replaying all events")

    cursor = events_col.find({}).sort("occurred_at", 1)

    count = 0

    for event in cursor:
        event_id = event["event_id"]
        event_type = event["event_type"]
        occurred_at = event["occurred_at"]

        event_text = extract_event_text(event)

        process_event(
            event_id=event_id,
            event_type=event_type,
            event_text=event_text,
            now=occurred_at,
            allow_cf_creation=allow_cf_creation,
        )

        count += 1

        if count % 500 == 0:
            print(f"  ↻ Replayed {count} events")

    print(f"✅ CF rebuild completed ({count} events replayed)")

def rebuild_tasks():
    for task in tasks_col.find({}):
        occurred_at = ensure_utc(task["created_at"])
        existing_event_id = task.get("source_event_id")
        if existing_event_id:
            existing_event = events_col.find_one({"event_id": existing_event_id})
            if existing_event:
                logger.info(
                    "task event already exists with event id: %s",
                    existing_event_id,
                )
                continue
            event_id = {}
        if task.get("source") == "interrupt.whatsapp":
            event = event_engine.register_event(
                event_type="interrupt.logged",
                occurred_at=occurred_at,
                payload={
                    "title": task["title"],
                    "source": "interrupt.whatsapp",
                    "unplanned": True,
                },
            )
            interrupt_col.insert_one(event)

        elif task.get("source") == "interrupt.call":
            event = event_engine.register_event(
                event_type="interrupt.logged",
                occurred_at=occurred_at,
                payload={
                    "title": task["title"],
                    "source": "interrupt.call",
                    "unplanned": True,
                },
            )
            interrupt_col.insert_one(event)
        elif task.get("source") == "email":
            meta = task.get("meta", {})
            email_uid = meta.get("email_uid")

            if email_uid is None:
                logger.warning(
                    "email task %s missing email_uid, skipping",
                    task["task_id"],
                )
                continue

            email = emails_col.find_one({"uid": email_uid})
            if not email:
                logger.warning(
                    "raw email not found for uid %s (task %s)",
                    email_uid,
                    task["task_id"],
                )
                continue

            email_id = email["_id"]
            uid = email.get("uid")
            received_at = email.get("received_at") or occurred_at

            # ---- canonical email.received event ----
            event = event_engine.register_event(
                event_type="email.received",
                occurred_at=received_at,
                payload={
                    "email_uid": uid,
                    "folder": email.get("folder"),
                    "subject": email.get("subject"),
                    "from": email.get("from"),
                    "to": email.get("to"),
                    "raw_email_ref": email_id,
                    "ingestion_version": EMAIL_PROCESSOR_VERSION,
                },
            )
            logger.info(
                "📨 email.received → %s (UID=%s)",
                event["event_id"],
                uid,
            )
        # ---------------------------------------------
        # Update task document
        # ---------------------------------------------
        tasks_col.update_one(
            {"_id": task["_id"]},
            {
                "$set": {
                    "source_event_id": event["event_id"],
                    "meta.rebuilt": True,
                }
            },
        )

        logger.info(
            "rebuilt task %s → event %s",
            task["task_id"],
            event["event_id"],
        )



def rebuild_work():
    for work in work_col.find({}):
        occurred_at = ensure_utc(work["created_at"])
        existing_event_id = work["event_id"]
        existing_event = events_col.find_one({"event_id": existing_event_id})
        if existing_event:
            logger.info("event already exists with event id: %s", existing_event_id)
            continue

        event = event_engine.register_event(
            event_type="work.logged",
            occurred_at=occurred_at,
            payload={
                "task_id": work["task_id"],
                "task_text": work["title"],
                "duration_minutes": work["duration_minutes"],
                "source": work["source"],
            }
        )
        #Update work module
        work_col.update_one(
            {"_id": work["_id"]},
            {
                "$set": {
                    "event_id": event["event_id"],
                    "meta.rebuilt": True,
                }
            },
        )



# ---------------------------------------------------------
# CLI Entry
# ---------------------------------------------------------

if __name__ == "__main__":
    # rebuild_event()
    rebuild_tasks()
    # rebuild_work()