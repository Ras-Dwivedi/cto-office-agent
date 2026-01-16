import logging
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from platform import system

from src.agents.judgement.event_matcher import get_match_for_text
from src.agents.task_manager.utils.event_engine import event_engine
from src.agents.task_manager.utils.work_engine import work_engine
from src.config.config import POMODORO_MINUTES
from src.db import get_collection
from src.llm.providers.client import llm

logger = logging.getLogger("pomodoro")


pomodoro = get_collection("pomodoro")

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
# Main CLI Entry
# =========================================================

def main(mode: str = "interactive"):
    """
    mode:
      - live        : start pomodoro immediately
      - log         : log past work (no timer)
      - interactive : ask user
    """

    work_col = get_collection("pomodoros")

    print("\n🍅 Work Logger\n")

    # -----------------------------
    # Mode selection
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
    # MANUAL WORK LOG (PAST WORK)
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
    # IMMUTABLE WORK EVENT
    # =====================================================
    try:
        event = event_engine.register_event(
            event_type="work.logged",
            occurred_at=end_time,
            payload={
                "task_id": task_id,
                "task_text": task_text,
                "duration_minutes": duration,
                "source": source,
            }
        )
        pomodoro.insert_one({
            "event_type": "work.logged",
            "occurred_at": end_time,
            "payload": {
                "task_id": task_id,
                "task_text": task_text,
                "duration_minutes": duration,
                "source": "pomodoro",
            },
            "created_at": utc_now(),
        })

        event_id = event.get("event_id")
        logger.info(f"logged pomodoro event {event_id}")
    except Exception:
        logger.exception("❌ Failed to register pomodoro event")
        return


    try:
        work = work_engine.record_work(
            event_id=event_id,
            title=task_text,
            started_at=start_time,
            ended_at=end_time,
            source="pomodoro",
        )

        logger.info(f"work logged pomodoro event {work['work_id']}")
    except Exception:
        logger.exception("❌ Failed to log work")


    print("\n✅ Work recorded successfully")

    if task_id:
        print(f"📝 Work linked to task: {task_id}")
    else:
        print("📝 Work recorded without task linkage")

    matching_texts = get_match_for_text(task_text)
    for i, m in enumerate(matching_texts, 1):

        # raw_obj = m.get("_raw")  # see note below

        print(f"\n#{i} MATCH")
        print("Type:", m["type"])
        print("ID:", m["id"])
        print("Probability:", m["match_probability"])
        print("Signals:", m["signals"])
        print("text:", m["preview"])

    advice = get_llm_advice(work,matching_texts)
    print(advice)


def build_llm_context(task_text, matching_texts, limit=5):
    top = sorted(
        matching_texts,
        key=lambda m: m["match_probability"],
        reverse=True
    )[:limit]

    return {
        "current_work": {
            "text": task_text
        },
        "matches": [
            {
                "type": m["type"],
                "id": m["id"],
                "probability": round(m["match_probability"], 3),
                "signals": m["signals"],
                "text": m["preview"]
            }
            for m in top
        ]
    }



def get_llm_advice(current_work, matches, limit=5):
    """
    current_work: dict with at least {"text": "..."}
    matches: list of match dicts from get_match_for_text()
    """

    SYSTEM_PROMPT = (
        "You are a work assistant.\n"
        "Use ONLY the provided matches.\n"
        "Do NOT invent tasks or facts.\n"
        "Respond in at most 3 sentences.\n"
        "If no clear next step exists, say so explicitly."
    )

    # ---- Defensive checks ----
    work_text = current_work.get("title", "").strip()
    if not work_text:
        return "No work description provided, so no advice can be generated."

    if not matches:
        return (
            "No relevant existing tasks or context were found. "
            "If this work is important, consider explicitly creating or updating a task."
        )

    # ---- Select & normalize top matches ----
    top_matches = sorted(
        matches,
        key=lambda m: m.get("match_probability", 0),
        reverse=True
    )[:limit]

    match_summaries = []
    for m in top_matches:
        match_summaries.append({
            "type": m.get("type"),
            "id": m.get("id"),
            "probability": round(m.get("match_probability", 0), 3),
            "signals": m.get("signals", {}),
            "text": m.get("preview", "")
        })

    # ---- Build prompt ----
    user_prompt = (
        "The user just completed the following work:\n\n"
        f"\"{work_text}\"\n\n"
        "Relevant context from the system:\n\n"
        f"{match_summaries}\n\n"
        "Based on this context:\n"
        "1. Say what this work most likely relates to\n"
        "2. Suggest the next concrete action the user should take"
    )

    # ---- LLM call ----
    advice = llm.complete(
        system=SYSTEM_PROMPT,
        user=user_prompt
    )

    return advice.strip()



# =========================================================

if __name__ == "__main__":
    main()
