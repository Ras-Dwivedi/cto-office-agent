from src.db import get_collection

def main(dry_run=True):
    tasks_col = get_collection("tasks")

    query = {
        "$or": [
            {"task_id": {"$exists": False}},
            {"task_id": None},
            {"task_id": ""}
        ]
    }

    count = tasks_col.count_documents(query)

    print(f"🧹 Found {count} task(s) without task_id")

    if count == 0:
        print("✅ Nothing to clean up")
        return

    if dry_run:
        print("⚠️ DRY RUN enabled — no documents deleted")
        print("   Run with dry_run=False to actually delete")
        return

    result = tasks_col.delete_many(query)

    print(f"🔥 Deleted {result.deleted_count} task(s)")

if __name__ == "__main__":
    # 🔒 First run with dry_run=True (default)
    main(dry_run=True)

    # After verifying output, uncomment the line below
    # main(dry_run=False)
