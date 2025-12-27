import time
import sys
import uuid
from datetime import datetime

from src.db import get_collection
from src.config.config import POMODORO_MINUTES

from src.agents.task_manager.utils.cf_engine import process_event
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
    pomodoros_col = get_collection("pomodoros")

    print("\n🍅 Pomodoro Session Started\n")

    task_text = input("Task name: ").strip()
    if not task_text:
        print("❌ Task name is required")
        return

    start_time = datetime.now()

    print(f"\n⏳ Working on '{task_text}' for {POMODORO_MINUTES} minutes")
    print("🧠 Context will be inferred automatically")
    print("Press Ctrl+C to abort\n")

    try:
        countdown(POMODORO_MINUTES)
    except KeyboardInterrupt:
        sys.stdout.write("\n⏹ Pomodoro cancelled. Nothing recorded.\n")
        return

    end_time = datetime.now()

    # -------------------------------------------------
    # Create Pomodoro Event (immutable fact)
    # -------------------------------------------------
    pomodoro_event_id = f"POMO-{uuid.uuid4().hex[:8]}"

    record_pomodoro(
        pomodoros_col=pomodoros_col,
        event_id=pomodoro_event_id,
        task_text=task_text,
        start_time=start_time,
        end_time=end_time,
        duration_minutes=POMODORO_MINUTES
    )

    # -------------------------------------------------
    # Centralized CF Processing (DB owned by CF engine)
    # -------------------------------------------------
    cf_hypotheses = process_event(
        event_id=pomodoro_event_id,
        event_type="pomodoro",
        event_text=task_text,
        now=end_time
    )

    # -------------------------------------------------
    # Update task state (CF-agnostic)
    # -------------------------------------------------
    status, desc = update_task_from_pomodoro(
        tasks_col=tasks_col,
        task_text=task_text
    )

    if status == "completed":
        print(f"\n✅ Task completed: {desc}")
    elif status == "progress":
        print(f"\n⏳ Progress recorded: {desc}")
    else:
        print(f"\n🆕 New task inferred: {desc}")

    print("\n🍅 Pomodoro recorded successfully")
    print("🔗 Context links inferred:")
    for h in cf_hypotheses:
        print(f"  - {h['cf_id']} (confidence={h['confidence']})")


if __name__ == "__main__":
    main()
