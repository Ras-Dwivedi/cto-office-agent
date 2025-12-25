from .db import tasks_col

def get_top_priority_tasks(limit=5):
    cursor = tasks_col.find(
        {
            "status": "OPEN"
        },
        {
            "_id": 0,
            "title": 1,
            "priority_score": 1,
            "due_by": 1,
            "stakeholder": 1,
            "owner": 1
        }
    ).sort("priority_score", -1).limit(limit)

    return list(cursor)

def get_prirotity_task():
    tasks = get_top_priority_tasks()

    print("\n🔥 TOP PRIORITY TASKS FOR TODAY\n")

    for i, t in enumerate(tasks, 1):
        print(
            f"{i}. {t['title']} "
            f"(score={t['priority_score']}, stakeholder={t['stakeholder']})"
        )

if __name__ == "__main__":
    get_prirotity_task()