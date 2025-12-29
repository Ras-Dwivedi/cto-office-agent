from src.db import get_collection
MAILBOX_NAME = "PRIMARY"


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
    print(f"\n🧹 Found {task_count} task(s) without task_id")

    if task_count > 0:
        if dry_run:
            print("⚠️ DRY RUN — tasks NOT deleted")
        else:
            result = tasks_col.delete_many(task_query)
            print(f"🔥 Deleted {result.deleted_count} task(s)")
    else:
        print("✅ No invalid tasks found")

def index_creator():
    def create_raw_email_index():
        emails_col = get_collection("raw_emails")

        try:
            emails_col.create_index(
                [
                    ("mailbox", 1),
                    ("folder", 1),
                    ("uid", 1),
                ],
                unique=True,
                name="uniq_mailbox_folder_uid",
            )
            print("✅ Unique index created on raw_emails(mailbox, folder, uid)")

        except Exception as e:
            if "already exists" in str(e):
                print("ℹ️ Index already exists")
            else:
                raise

    if __name__ == "__main__":
        create_raw_email_index()


if __name__ == "__main__":
    # -------------------------------------------------
    # FIRST RUN (SAFE)
    # -------------------------------------------------
    # main(dry_run=True)
    index_creator()
    # -------------------------------------------------
    # AFTER VERIFYING OUTPUT, RUN:
    # main(dry_run=False)
    # -------------------------------------------------
