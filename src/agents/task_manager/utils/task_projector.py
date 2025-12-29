# src/agents/task_manager/task_projector.py

import logging
from datetime import datetime
from typing import Dict

from src.db import get_collection
from src.agents.task_manager.utils.task_engine import task_engine

logger = logging.getLogger("task_projector")

events_col = get_collection("events")


class TaskProjector:
    """
    Projects events into task state.
    Safe to run multiple times (idempotent).
    """

    def process_event(self, event: Dict):
        intent = event.get("task_intent")

        if not intent or not intent.get("should_create"):
            return None

        title = intent.get("title")
        source = intent.get("source", event["event_type"])

        if not title:
            logger.warning(
                "Task intent without title for event %s",
                event["event_id"]
            )
            return None

        task = task_engine.create_task(
            title=title,
            source=source,
            source_ref=event["event_id"],
            created_at=event["occurred_at"],
            extra={
                "signals": intent.get("signals", {}),
                "event_id": event["event_id"],
            },
        )

        # back-link event → task
        events_col.update_one(
            {"event_id": event["event_id"]},
            {"$set": {"task_id": task["task_id"]}}
        )

        logger.info(
            "Task %s projected from event %s",
            task["task_id"],
            event["event_id"]
        )

        return task


task_projector = TaskProjector()
