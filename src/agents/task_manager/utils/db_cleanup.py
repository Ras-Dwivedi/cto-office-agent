from src.db import get_collection


def main(dry_run=True):
    edges_col = get_collection("event_cf_edges")
    tasks_col = get_collection("tasks")

    # -------------------------------------------------
    # STEP 1: Delete TASK-None edges
    # -------------------------------------------------
    edge_query = {
        "event_id": "TASK-None"
    }

    edge_count = edges_col.count_documents(edge_query)
    print(f"🧹 Found {edge_count} event edge(s) with event_id = 'TASK-None'")

    if edge_count > 0:
        if dry_run:
            print("⚠️ DRY RUN — TASK-None edges NOT deleted")
        else:
            result = edges_col.delete_many(edge_query)
            print(f"🔥 Deleted {result.deleted_count} TASK-None edge(s)")
    else:
        print("✅ No TASK-None edges found")

    # -------------------------------------------------
    # STEP 2: Delete tasks without task_id
    # -------------------------------------------------
    task_query = {
        "$or": [
            {"task_id": {"$exists": False}},
            {"task_id": None},
            {"task_id": ""}
        ]
    }

    task_count = tasks_col.count_documents(task_query)
    print(f"\n🧹 Found {task_count} task_
