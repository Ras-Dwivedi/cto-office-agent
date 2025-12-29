# src/task_engine3.py

from datetime import datetime


def find_matching_task(tasks_col, cf_id, task_text):
    return tasks_col.find_one({
        "cf_id": cf_id,
        "status": "pending",
        "description": {"$regex": task_text, "$options": "i"}
    })


def update_task_from_pomodoro(tasks_col, cf_id, task_text):
    task = find_matching_task(tasks_col, cf_id, task_text)

    if task:
        pomos = task.get("pomodoros_spent", 0) + 1
        tasks_col.update_one(
            {"_id": task["_id"]},
            {"$set": {"pomodoros_spent": pomos, "last_updated": datetime.now()}}
        )

        if pomos >= task.get("estimated_pomodoros", 1):
            tasks_col.update_one(
                {"_id": task["_id"]},
                {"$set": {
                    "status": "completed",
                    "completed_at": datetime.now()
                }}
            )
            return "completed", task["description"]

        return "progress", task["description"]

    # Create implicit task
    tasks_col.insert_one({
        "cf_id": cf_id,
        "description": task_text,
        "status": "pending",
        "pomodoros_spent": 1,
        "estimated_pomodoros": 1,
        "created_at": datetime.now()
    })

    return "created", task_text
