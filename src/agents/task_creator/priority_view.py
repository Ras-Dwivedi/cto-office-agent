from src.db import  get_collection
tasks_col = get_collection("tasks")


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

def main():
    get_prirotity_task()

if __name__ == "__main__":
    main()