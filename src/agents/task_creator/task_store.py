from datetime import datetime
from src.db import get_collection

tasks_col = get_collection("tasks")


def store_task(tasks):
    """
    Store one or more tasks idempotently.
    """

    if isinstance(tasks, dict):
        tasks = [tasks]

    now = datetime.utcnow().isoformat()

    for task in tasks:
        # Never reuse Mongo _id
        task.pop("_id", None)

        # Ensure timestamps
        created_at = task.get("created_at", now)
        task["last_activity_at"] = now
        task.setdefault("status", "OPEN")

        # IMPORTANT:
        # Remove created_at from $set payload to avoid conflict
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
