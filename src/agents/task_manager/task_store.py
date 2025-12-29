import uuid
from datetime import datetime

from src.db import get_collection

tasks_col = get_collection("tasks")


def store_task(tasks):
    """
    Store one or more tasks idempotently.
    Ensures every task has a stable task_id.
    """

    if isinstance(tasks, dict):
        tasks = [tasks]

    now = datetime.utcnow().isoformat()

    for task in tasks:
        # Never reuse Mongo _id
        task.pop("_id", None)

        # -------------------------------------------------
        # 🔑 ENSURE TASK ID (SOURCE OF TRUTH)
        # -------------------------------------------------
        if not task.get("task_id"):
            task["task_id"] = f"TASK-{uuid.uuid4().hex[:8]}"

        # Ensure timestamps & defaults
        created_at = task.get("created_at", now)
        task["last_activity_at"] = now
        task.setdefault("status", "OPEN")

        # Avoid updating created_at on existing docs
        task_without_created = dict(task)
        task_without_created.pop("created_at", None)

        tasks_col.update_one(
            {
                "email_uid": task.get("email_uid"),
                "title": task.get("title")
            },
            {
                "$set": task_without_created,
                "$setOnInsert": {
                    "created_at": created_at
                }
            },
            upsert=True
        )
