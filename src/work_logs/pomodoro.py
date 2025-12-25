import time
from datetime import datetime
from src.db import get_collection

POMODORO_MINUTES = 25

def main():
    tasks_col = get_collection("tasks")

    print("\n🍅 Pomodoro Session Started\n")

    task_name = input("Task name: ").strip()
    if not task_name:
        print("❌ Task name is required")
        return

    start_time = datetime.now()
    print(f"\n⏳ Working on '{task_name}' for {POMODORO_MINUTES} minutes...")
    print("Press Ctrl+C to abort\n")

    try:
        time.sleep(POMODORO_MINUTES * 60)
    except KeyboardInterrupt:
        print("\n⛔ Pomodoro aborted")
        return

    end_time = datetime.now()

    print("\n⏰ Time's up!")

    completed = input("Is the task completed? (Y/N): ").strip().lower()

    task_doc = {
        "task_name": task_name,
        "started_at": start_time,
        "ended_at": end_time,
        "duration_minutes": POMODORO_MINUTES,
        "completed": completed == "y",
        "method": "pomodoro",
        "source": "work_logs",
        "created_at": datetime.now()
    }

    if completed != "y":
        next_review = input("Next review date (YYYY-MM-DD): ").strip()
        task_doc["next_review_date"] = next_review
    else:
        task_doc["next_review_date"] = None

    tasks_col.insert_one(task_doc)

    status = "✅ Completed" if task_doc["completed"] else "⏭ Deferred"
    print(f"\n{status}: '{task_name}' recorded in MongoDB")

if __name__ == "__main__":
    main()
