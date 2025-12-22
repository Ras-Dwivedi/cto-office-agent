from .db import tasks_col
from .priority import compute_priority

def store_tasks(tasks, email_uid):
    for task in tasks:
        task["priority_score"] = compute_priority(task)
        task["status"] = "OPEN"
        task["source"] = "email"
        task["email_uid"] = email_uid

        tasks_col.insert_one(task)
