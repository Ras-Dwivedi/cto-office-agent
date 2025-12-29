import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.agents.task_manager.utils.project_resolver import resolve_project_id
from src.agents.task_manager.utils.task_id import generate_task_id
from src.agents.task_manager.utils.verb_resolver import resolve_task_verb
from src.db import get_collection

logger = logging.getLogger("task_engine")

# =========================================================
# DB
# =========================================================

tasks_col = get_collection("tasks")

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
    Central authority for TASK state & LOAD.

    Task = work that needs to be done.
    Every task MUST originate from an event.
    """

    # -----------------------------------------------------
    # CREATE TASK (from event)
    # -----------------------------------------------------

    def create_task(
        self,
        *,
        title: str,
        source: str,
        source_event_id: str,
        occurred_at: Optional[datetime] = None,
        signals: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a task deterministically from an event.

        Called ONLY by EventEngine.
        """

        occurred_at = ensure_utc(occurred_at)
        signals = signals or {}
        meta = meta or {}

        project_id = resolve_project_id(meta)
        verb = resolve_task_verb({"title": title})

        task_id = generate_task_id(
            project_id=project_id,
            verb=verb,
            title=title,
        )

        doc = {
            "task_id": task_id,
            "title": title,

            # ---- classification ----
            "project_id": project_id,
            "task_verb": verb,

            # ---- lifecycle ----
            "status": "OPEN",
            "created_at": occurred_at,
            "last_activity_at": occurred_at,

            # ---- provenance ----
            "source": source,
            "source_event_id": source_event_id,

            # ---- load (canonical) ----
            "load": {
                "work_minutes": 0,
                "interrupt_count": 0,
            },

            # ---- signals (from extraction) ----
            "signals": {
                "institutional": signals.get("institutional"),
                "delegatable": signals.get("delegatable"),
                "blocks_others": signals.get("blocks_others"),
                "external_dependency": signals.get("external_dependency"),
                "due_by": signals.get("due_by"),
            },

            # ---- opaque metadata ----
            "meta": meta,
        }

        tasks_col.update_one(
            {"task_id": task_id},
            {"$setOnInsert": doc},
            upsert=True,
        )

        logger.info("Task created %s from event %s", task_id, source_event_id)
        return doc

    # -----------------------------------------------------
    # APPLY WORK (pomodoro / manual)
    # -----------------------------------------------------

    def apply_work(
        self,
        *,
        task_id: str,
        minutes: int,
        occurred_at: Optional[datetime] = None,
    ) -> None:
        if minutes <= 0:
            raise ValueError("Work minutes must be positive")

        occurred_at = ensure_utc(occurred_at)

        result = tasks_col.update_one(
            {"task_id": task_id},
            {
                "$set": {"last_activity_at": occurred_at},
                "$inc": {"load.work_minutes": minutes},
            },
        )

        if result.matched_count == 0:
            raise ValueError(f"Task not found: {task_id}")

    # -----------------------------------------------------
    # APPLY INTERRUPT
    # -----------------------------------------------------

    def apply_interrupt(
        self,
        *,
        task_id: str,
        occurred_at: Optional[datetime] = None,
    ) -> None:

        occurred_at = ensure_utc(occurred_at)

        result = tasks_col.update_one(
            {"task_id": task_id},
            {
                "$set": {"last_activity_at": occurred_at},
                "$inc": {"load.interrupt_count": 1},
            },
        )

        if result.matched_count == 0:
            raise ValueError(f"Task not found: {task_id}")

    # -----------------------------------------------------
    # COMPLETE TASK
    # -----------------------------------------------------

    def mark_completed(
        self,
        *,
        task_id: str,
        occurred_at: Optional[datetime] = None,
        reason: Optional[str] = None,
    ) -> None:

        occurred_at = ensure_utc(occurred_at)

        tasks_col.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    "status": "COMPLETED",
                    "completed_at": occurred_at,
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
# Singleton
# =========================================================

task_engine = TaskEngine()
