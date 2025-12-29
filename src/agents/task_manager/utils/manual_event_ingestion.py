import uuid
import logging
from datetime import datetime, timezone

from src.agents.task_manager.utils.cf_engine import process_event
from src.agents.task_manager.utils.event_engine import event_engine

logger = logging.getLogger("manual_event_ingestion")


# =========================================================
# Utilities
# =========================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# =========================================================
# Main
# =========================================================

def main(source: str | None = None):
    """
    Manual interrupt ingestion.

    Architectural rules:
    - Interrupts ARE tasks
    - Tasks are created ONLY via EventEngine
    - CF links to EVENTS, not tasks
    """

    print("\n📱 Interrupt Logger (Unplanned Work)\n")

    # -----------------------------
    # Source resolution
    # -----------------------------
    if source not in {"whatsapp", "call"}:
        source = input("Source (whatsapp / call): ").strip().lower()

    if source not in {"whatsapp", "call"}:
        print("❌ Invalid source")
        return

    # -----------------------------
    # Summary
    # -----------------------------
    title = input("Interrupt summary (one line): ").strip()
    if not title:
        print("❌ Summary required")
        return

    now = utc_now()

    # =====================================================
    # 1️⃣ REGISTER EVENT (single source of truth)
    # =====================================================
    try:
        event = event_engine.register_event(
            event_type="interrupt.logged",
            occurred_at=now,
            payload={
                "title": title,
                "source": source,
                "unplanned": True,
            }
        )



    except Exception:
        logger.exception("Failed to register interrupt event")
        print("❌ Failed to register interrupt")
        return

    event_id = event["event_id"]
    task_id = event.get("task_id")

    # =====================================================
    # 2️⃣ CF INFERENCE (meaning layer)
    # =====================================================
    try:
        process_event(
            event_id=event_id,
            event_type=event["event_type"],
            event_text=title,
            now=now,
        )
    except Exception:
        logger.exception("CF processing failed for interrupt")

    # =====================================================
    # Feedback
    # =====================================================
    print("\n✅ Interrupt registered as task")
    print(f"🧾 Task ID : {task_id}")
    print(f"📌 Source  : interrupt.{source}")
    print("🧠 Context inferred")


# =========================================================

if __name__ == "__main__":
    main()
