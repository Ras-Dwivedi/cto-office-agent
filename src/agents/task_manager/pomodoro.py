import time
import sys
import uuid
import logging
from datetime import datetime, timezone, timedelta

from src.db import get_collection
from src.config.config import POMODORO_MINUTES
from src.agents.task_manager.utils.cf_engine import process_event
from src.agents.task_manager.utils.task_engine import update_task_from_pomodoro

logger = logging.getLogger("pomodoro")


# =========================================================
# Utilities
# =========================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def countdown(minutes: int):
    total_seconds = minutes * 60
    for remaining in range(total_seconds, -1, -1):
        mins, secs = divmod(remaining, 60)
        sys.stdout.write(f"\r⏳ Time remaining: {mins:02d}:{secs:02d}")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\n")


# =========================================================
# Pomodoro Recorder (IMMUTABLE EVENT)
# =========================================================

def record_pomodoro(
    *,
    pomodoros_col,
    pomodoro_id: str,
    task_text: str,
    start: datetime,
    end: datetime,
    duration_minutes: int,
    task_id: str | None,
    source: str,
):
    pomodoros_col.insert_one({
        "pomodoro_id": pomodoro_id,
        "task_id": task_id,
        "task_hint": task_text,
        "started_at": start,
        "ended_at": end,
        "duration_minutes": duration_minutes,
        "created_at": utc_now(),
        "source": source,
    })


# =========================================================
# Main CLI Entry
# =========================================================

def main(mode: str = "interactive"):
    """
    mode:
      - live        : start pomodoro immediately
      - log         : log past work (no timer)
      - interactive : ask user
    """

    pomodoros_col = get_collection("pomodoros")
    tasks_col = get_collection("tasks")

    print("\n🍅 Work Logger\n")

    # -----------------------------
    # Mode resolution
    # -----------------------------
    if mode == "interactive":
        print("How do you want to log work?")
        print("1. Start Pomodoro now")
        print("2. Log past work")

        choice = input("Choose [1/2]: ").strip()
        if choice == "1":
            mode = "live"
        elif choice == "2":
            mode = "log"
        else:
            print("❌ Invalid choice")
            return

    if mode not in {"live", "log"}:
        print("❌ Invalid mode")
        return

    # -----------------------------
    # Common inputs
    # -----------------------------
    task_text = input("Task name / short description: ").strip()
    if not task_text:
        print("❌ Task description is required")
        return

    task_id = input("Optional task_id (press Enter to skip): ").strip() or None

    # =====================================================
    # LIVE POMODORO
    # =====================================================
    if mode == "live":
        start_time = utc_now()

        print(f"\n⏳ Working on '{task_text}' for {POMODORO_MINUTES} minutes")
        print("🧠 Context will be inferred automatically")
        print("Press Ctrl+C to abort\n")

        try:
            countdown(POMODORO_MINUTES)
        except KeyboardInterrupt:
            print("\n⏹ Pomodoro cancelled. Nothing recorded.")
            return

        end_time = utc_now()
        duration = POMODORO_MINUTES
        source = "pomodoro"

    # =====================================================
    # MANUAL LOG (PAST WORK)
    # =====================================================
    else:
        mins = input("How many minutes did you work? ").strip()
        try:
            duration = int(mins)
            if duration <= 0:
                raise ValueError
        except ValueError:
            print("❌ Invalid duration")
            return

        end_time = utc_now()
        start_time = end_time - timedelta(minutes=duration)
        source = "manual"

    # =====================================================
    # Persist work event
    # =====================================================
    pomodoro_id = f"WORK-{uuid.uuid4().hex[:8]}"

    record_pomodoro(
        pomodoros_col=pomodoros_col,
        pomodoro_id=pomodoro_id,
        task_text=task_text,
        start=start_time,
        end=end_time,
        duration_minutes=duration,
        task_id=task_id,
        source=source,
    )

    # =====================================================
    # CF Inference (graph-owned)
    # =====================================================
    cf_hypotheses = process_event(
        event_id=pomodoro_id,
        event_type="work",
        event_text=task_text,
        now=end_time,
    )

    # =====================================================
    # Optional task update
    # =====================================================
    if task_id:
        try:
            status, desc = update_task_from_pomodoro(
                tasks_col=tasks_col,
                task_id=task_id
            )
        except Exception:
            logger.exception("Failed to update task from work log")
            status, desc = "error", "Task update failed"
    else:
        status, desc = "unlinked", "Work recorded without task linkage"

    # =====================================================
    # User feedback
    # =====================================================
    print("\n✅ Work recorded successfully")

    if status == "completed":
        print(f"🎯 Task completed: {desc}")
    elif status == "progress":
        print(f"⏳ Task progress recorded: {desc}")
    else:
        print(f"📝 {desc}")

    if cf_hypotheses:
        print("\n🔗 Contexts inferred:")
        for h in cf_hypotheses:
            print(f"  - {h['cf_id']} (confidence={h['confidence']})")
    else:
        print("\n🔗 No context inferred")


# =========================================================

if __name__ == "__main__":
    main()
