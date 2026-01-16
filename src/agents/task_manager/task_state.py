import json
from datetime import datetime
from src.db import get_collection
from bson import ObjectId

tasks_col = get_collection("tasks")


# -------------------------
# Internal helpers
# -------------------------

def _find_by_task_id(task_id: str) -> dict:
    """
    Resolve a single task document using the human-readable `task_id`.

    This function enforces `task_id` uniqueness as a safety guarantee before
    allowing any state mutation (close, drop, start, wait).

    Behavior:
    - Queries the tasks collection for documents matching the given `task_id`.
    - If no task is found, prints a warning and returns None.
    - If multiple tasks are found (data integrity violation), prints an error,
      refuses to act, and returns None.
    - If exactly one task is found, returns the full task document.

    Design rationale:
    - Prevents accidental modification of the wrong task.
    - Treats non-unique `task_id` as a hard safety failure.
    - Keeps MongoDB `_id` usage internal and invisible to the CLI layer.

    Parameters:
        task_id (str): Human-readable task identifier
                       (e.g. "TASK::UNASSIGNED::DEV::F0AE11")

    Returns:
        dict | None:
            - The task document if resolution is successful.
            - None if the task does not exist or uniqueness is violated.

    Side effects:
        - Prints user-facing warnings/errors for missing or ambiguous task IDs.
        - Does not raise exceptions (safe for CLI usage).

    Notes:
        This function must be used as the sole resolver for task mutations.
        Direct updates using MongoDB `_id` from the CLI are intentionally avoided.
    """

    matches = list(tasks_col.find({"task_id": task_id}))

    if not matches:
        print(f"⚠️ Task not found: {task_id}")
        return None

    if len(matches) > 1:
        print(f"❌ Multiple tasks found for task_id={task_id}")
        print("Refusing to act. Fix data integrity first.")
        return None

    return matches[0]


def _update(task_id: str, status: str, extra: dict | None = None):
    task = _find_by_task_id(task_id)
    if not task:
        return

    update = {
        "status": status,
        "last_activity_at": datetime.utcnow(),
    }

    if extra:
        update.update(extra)

    tasks_col.update_one(
        {"_id": task["_id"]},
        {"$set": update}
    )

    print(f"✅ Task {task_id} marked as {status}")



def _json_safe(obj):
    """
    Recursively convert MongoDB/Python-specific types
    into JSON-serializable representations.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, ObjectId):
        return str(obj)

    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]

    return obj


# -------------------------
# Public task actions
# -------------------------

def close_task(task_id: str):
    _update(
        task_id,
        "DONE",
        {
            "closed_at": datetime.utcnow(),
            "close_reason": "manual",
        },
    )


def drop_task(task_id: str):
    _update(
        task_id,
        "DROPPED",
        {
            "closed_at": datetime.utcnow(),
            "close_reason": "dropped",
        },
    )


def start_task(task_id: str):
    _update(task_id, "IN_PROGRESS")


def wait_task(task_id: str):
    _update(task_id, "WAITING")


def show_task(task_id: str):
    task = _find_by_task_id(task_id)

    if not task:
        print(f"No such task or error in fetching task {task_id}")
        return

    # Remove internal Mongo ID
    task.pop("_id", None)

    # Normalize for JSON
    safe_task = _json_safe(task)

    print(json.dumps(safe_task, indent=2))


# -------------------------
# Listing
# -------------------------

def list_tasks():
    tasks = tasks_col.find({"status": "OPEN"})

    print("\n📋 OPEN TASKS\n")
    for t in tasks:
        print(f"- {t['title']}")
        print(f"  task_id: {t['task_id']}| Created at: {t['created_at']}")
        print(f"  project: {t.get('project_id')} | verb: {t.get('task_verb')}")
        print()


def print_help():
    print(
        """
🧭 TASK COMMAND HELP

Usage:
  task
      Show morning judgment brief (delegate vs personal focus)

  task list
      List all OPEN tasks

  task close <task_id>
      Mark a task as DONE

  task drop <task_id>
      Mark a task as DROPPED (intentionally discarded)

  task start <task_id>
      Mark a task as IN_PROGRESS

  task wait <task_id>
      Mark a task as WAITING (blocked or delegated)

Notes:
  • <task_id> is the human-readable task identifier
    (e.g. TASK::UNASSIGNED::DEV::F0AE11)
  • Mongo _id is NOT required
  • Actions are idempotent and safe

Examples:
  task
  task list
  task close TASK::UNASSIGNED::DEV::F0AE11
  task drop TASK::UNASSIGNED::DEV::DEV::A91C02
"""
    )
