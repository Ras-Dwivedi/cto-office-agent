import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.db import get_collection
from src.agents.task_manager.utils.task_id import generate_task_id
from src.agents.task_manager.utils.verb_resolver import resolve_task_verb
from src.agents.task_manager.utils.project_resolver import resolve_project_id

logger = logging.getLogger("task_engine")

# =========================================================
# DB
# =========================================================

tasks_col = get_collection("tasks")

# =========================================================
# Constants
# =========================================================

ALLOWED_SOURCES = {
    "email",
    "decision",
    "work",
    "call",
    "whatsapp",
    "manual",
}

# =========================================================
# Time helpers
# =========================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return utc_now()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

# =========================================================
# Task Engine
# =========================================================

class TaskEngine:
    """
    Central authority for ALL task lifecycle operations.

    RULES:
    - Agents MUST NOT write directly to MongoDB
    - Agents MUST NOT infer task completion
    - All mutations flow through this engine
    """

    # -----------------------------------------------------
    # CREATE TASK (email / decision / interrupt)
    # -----------------------------------------------------

    def create_task(
        self,
        *,
        title: str,
        source: str,
        source_ref: Optional[str] = None,
        created_at: Optional[datetime] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if source not in ALLOWED_SOURCES:
            raise ValueError(f"Invalid task source: {source}")

        created_at = ensure_utc(created_at)
        extra = extra or {}

        project_id = resolve_project_id(extra)
        verb = resolve_task_verb({"title": title})

        task_id = generate_task_id(
            project_id=project_id,
            verb=verb,
            title=title,
        )

        doc = {
            "task_id": task_id,
            "title": title,
            "project_id": project_id,
            "task_verb": verb,

            "status": "OPEN",

            "created_at": created_at,
            "last_activity_at": created_at,

            "source": source,
            "source_ref": source_ref,

            # -------- LOAD (canonical) --------
            "load": {
                "work_minutes": 0,
                "interrupt_count": 0,
            },

            # -------- metadata --------
            "meta": extra,
        }

        try:
            tasks_col.update_one(
                {"task_id": task_id},
                {"$setOnInsert": doc},
                upsert=True,
            )
        except Exception:
            logger.exception("Failed to create task %s", task_id)
            raise

        return doc

    # -----------------------------------------------------
    # APPLY WORK (pomodoro / manual log)
    # -----------------------------------------------------

    def apply_work(
        self,
        *,
        task_id: str,
        minutes: int,
        event_time: Optional[datetime] = None,
        source: str = "work",
    ) -> Dict[str, Any]:

        if minutes <= 0:
            raise ValueError("Work minutes must be positive")

        event_time = ensure_utc(event_time)

        result = tasks_col.update_one(
            {"task_id": task_id},
            {
                "$set": {"last_activity_at": event_time},
                "$inc": {"load.work_minutes": minutes},
            },
        )

        if result.matched_count == 0:
            raise ValueError(f"Task not found: {task_id}")

        return {
            "task_id": task_id,
            "work_minutes_added": minutes,
            "source": source,
        }

    # -----------------------------------------------------
    # APPLY INTERRUPT (call / whatsapp)
    # -----------------------------------------------------

    def apply_interrupt(
        self,
        *,
        title: str,
        source: str,
        event_time: Optional[datetime] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        if source not in {"call", "whatsapp"}:
            raise ValueError("Invalid interrupt source")

        event_time = ensure_utc(event_time)

        if task_id:
            tasks_col.update_one(
                {"task_id": task_id},
                {
                    "$set": {"last_activity_at": event_time},
                    "$inc": {"load.interrupt_count": 1},
                },
            )
            return {
                "task_id": task_id,
                "interrupt": True,
                "source": source,
            }

        # No task_id → create lightweight interrupt task
        return self.create_task(
            title=title,
            source=source,
            created_at=event_time,
            extra={"interrupt": True},
        )

    # -----------------------------------------------------
    # COMPLETE TASK
    # -----------------------------------------------------

    def mark_completed(
        self,
        *,
        task_id: str,
        completed_at: Optional[datetime] = None,
        reason: Optional[str] = None,
    ) -> None:

        completed_at = ensure_utc(completed_at)

        tasks_col.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    "status": "COMPLETED",
                    "completed_at": completed_at,
                    "completion_reason": reason,
                }
            },
        )

    # -----------------------------------------------------
    # READ HELPERS
    # -----------------------------------------------------

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return tasks_col.find_one({"task_id": task_id}, {"_id": 0})

# =========================================================
# Event → Task Dispatcher (PUBLIC API)
# =========================================================

def process_task_event(
    *,
    event_type: str,
    task_id: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    title: Optional[str] = None,
    source: str = "work",
    event_time: Optional[datetime] = None,
) -> tuple[str, str]:
    """
    Canonical event-to-task mutation handler.

    Returns:
        (status, description)
    """

    try:
        # ---------------------------
        # WORK EVENT
        # ---------------------------
        if event_type == "work":
            if not task_id:
                return "unlinked", "Work recorded without task linkage"

            if not duration_minutes or duration_minutes <= 0:
                raise ValueError("Work event requires positive duration")

            task_engine.apply_work(
                task_id=task_id,
                minutes=duration_minutes,
                event_time=event_time,
                source=source,
            )

            return "progress", f"{duration_minutes} minutes added"

        # ---------------------------
        # INTERRUPT EVENT
        # ---------------------------
        if event_type == "interrupt":
            if not title:
                raise ValueError("Interrupt requires title")

            result = task_engine.apply_interrupt(
                task_id=task_id,
                title=title,
                source=source,
                event_time=event_time,
            )

            return "interrupt", f"Interrupt recorded ({result.get('task_id')})"

        # ---------------------------
        # COMPLETE EVENT
        # ---------------------------
        if event_type == "complete":
            if not task_id:
                raise ValueError("Completion requires task_id")

            task_engine.mark_completed(
                task_id=task_id,
                completed_at=event_time,
            )

            return "completed", "Task marked as completed"

        # ---------------------------
        # UNKNOWN EVENT
        # ---------------------------
        raise ValueError(f"Unsupported task event type: {event_type}")

    except Exception as e:
        logger.exception("Task event processing failed")
        return "error", str(e)


# =========================================================
# Singleton (recommended usage)
# =========================================================

task_engine = TaskEngine()
