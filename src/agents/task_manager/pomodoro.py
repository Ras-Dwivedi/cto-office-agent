import time
import sys

from datetime import datetime
from src.db import get_collection
from src.config.config import POMODORO_MINUTES

from src.agents.task_manager.utils.context_fingerprint import find_or_create_cf
from src.agents.task_manager.utils.task_engine import update_task_from_pomodoro
from src.agents.task_manager.utils.pomodoro_recorder import record_pomodoro

def countdown(minutes: int):
    total_seconds = minutes * 60

    for remaining in range(total_seconds, -1, -1):
        mins, secs = divmod(remaining, 60)
        timer = f"⏳ Time remaining: {mins:02d}:{secs:02d}"
        sys.stdout.write("\r" + timer)
        sys.stdout.flush()
        time.sleep(1)

    sys.stdout.write("\n")


def main():
    tasks_col = get_collection("tasks")
    contexts_col = get_collection("contexts")
    pomodoros_col = get_collection("pomodoros")

    print("\n🍅 Pomodoro Session Started\n")

    task_text = input("Task name: ").strip()
    if not task_text:
        print("❌ Task name is required")
        return

    start_time = datetime.now()

    # 🔹 Context inference
    cf = find_or_create_cf(task_text, contexts_col, start_time)

    print(f"\n⏳ Working on '{task_text}' for {POMODORO_MINUTES} minutes")
    print(f"🧠 Context: {cf['title']}")
    print("Press Ctrl+C to abort\n")

    try:
        countdown(POMODORO_MINUTES)
    except KeyboardInterrupt:
        sys.stdout.write("\n⏹ Pomodoro cancelled. Nothing recorded.\n")
        return

    end_time = datetime.now()

    # 🔹 Record pomodoro
    record_pomodoro(
        pomodoros_col,
        cf["cf_id"],
        task_text,
        start_time,
        end_time,
        POMODORO_MINUTES
    )

    # 🔹 Update context
    contexts_col.update_one(
        {"cf_id": cf["cf_id"]},
        {
            "$set": {"last_activity": end_time},
            "$inc": {
                "total_pomodoros": 1,
                "total_time_minutes": POMODORO_MINUTES
            }
        }
    )

    # 🔹 Update task state
    status, desc = update_task_from_pomodoro(
        tasks_col,
        cf["cf_id"],
        task_text
    )

    if status == "completed":
        print(f"\n✅ Task completed: {desc}")
    elif status == "progress":
        print(f"\n⏳ Progress recorded: {desc}")
    else:
        print(f"\n🆕 New task inferred: {desc}")

    print("\n🍅 Pomodoro recorded successfully")


if __name__ == "__main__":
    main()
