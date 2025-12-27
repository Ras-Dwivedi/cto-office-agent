from src.db import get_collection

tasks_col = get_collection("tasks")


def get_top_priority_tasks(limit=5):
    cursor = tasks_col.find(
        {"status": "OPEN"},
        {
            "_id": 0,
            "task_id": 1,
            "title": 1,
            "priority_score": 1,
            "stakeholder": 1,
            "project_id": 1,
            "task_verb": 1,
        }
    ).sort("priority_score", -1).limit(limit)

    return list(cursor)


def get_priority_task():
    tasks = get_top_priority_tasks()

    print("\n🔥 TOP PRIORITY TASKS FOR TODAY\n")

    if not tasks:
        print("(No open priority tasks)")
        return

    for i, t in enumerate(tasks, 1):
        print(f"{i}. {t['title']}")
        print(f"   🆔 Task ID   : {t.get('task_id')}")
        print(f"   ⭐ Score     : {t.get('priority_score')}")
        print(f"   👤 Stakeholder : {t.get('stakeholder')}")
        print(f"   📁 Project  : {t.get('project_id')} | Verb: {t.get('task_verb')}")
        print()
