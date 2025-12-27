from src.db import get_collection


def main():
    edges_col = get_collection("event_cf_edges")

    query = {
        "event_id": "TASK-None"
    }

    count = edges_col.count_documents(query)
    print(f"🧹 Found {count} edge(s) with event_id = 'TASK-None'")

    if count == 0:
        print("✅ Nothing to delete")
        return

    result = edges_col.delete_many(query)
    print(f"🔥 Deleted {result.deleted_count} edge(s)")


if __name__ == "__main__":
    main()
