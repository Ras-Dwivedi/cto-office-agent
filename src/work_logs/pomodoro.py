import time
from datetime import datetime, date
from src.db import get_collection
from src.config import POMODORO_MINUTES

def main():
    tasks_col = get_collection("completed_tasks")

    print("\n🍅 Pomodoro Session Started\n")

    task_name = input("Task name: ").strip()
    if not task_name:
        print("❌ Task name is required")
        return

    start_time = datetime.now()
    print(f"\n⏳ Working on '{task_name}' for {POMODORO_MINUTES} minutes...")
    print("Press Ctrl+C to abort\n")

    try:
        time.sleep(POMODORO_MINUTES*60)
        finished_naturally = True
    except KeyboardInterrupt:
        finished_naturally = False
        print("\n⏹ Pomodoro interrupted")

        finish_now = input(
            "Did you finish the task early? (Y/N): "
        ).strip().lower()

        if finish_now != "y":
            print("❌ Pomodoro cancelled. Nothing recorded.")
            return


    end_time = datetime.now()

    print("\n⏰ Time's up!")

    completed = input("Is the task completed? (Y/N): ").strip().lower().startswith("y")

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
    if not completed:
        next_review = input("Next review date (YYYY-MM-DD, optional): ").strip()
        if next_review:
            try:
                task_doc["next_review_date"] = date.fromisoformat(next_review)
            except ValueError:
                print("⚠️ Invalid date format. Review date not stored.")
                task_doc["next_review_date"] = None
        else:
            task_doc["next_review_date"] = None

    else:
        task_doc["next_review_date"] = None

    tasks_col.insert_one(task_doc)

    status = "✅ Completed" if task_doc["completed"] else "⏭ Deferred"
    print(f"\n{status}: '{task_name}' recorded in MongoDB")


if __name__ == "__main__":
    main()
