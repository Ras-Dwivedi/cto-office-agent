import logging
from datetime import datetime, timezone, timedelta

from src.agents.task_manager.utils.event_engine import event_engine
from src.agents.task_manager.utils.task_engine import task_engine
from src.agents.task_manager.utils.work_engine import work_engine
from src.db import get_collection
logger = logging.getLogger("manual_event_ingestion")

interrupt_col = get_collection("interrupt")

# =========================================================
# Utilities
# =========================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def classify_interrupt(text: str) -> str:
    """
    Lightweight heuristic classification.
    Returns: "task" | "work"
    """

    text_l = text.lower()

    work_markers = [
        "handled", "fixed", "resolved", "discussed",
        "explained", "clarified", "helped", "walked through"
    ]

    task_markers = [
        "need to", "follow up", "review", "prepare",
        "send", "create", "check", "update"
    ]

    if any(w in text_l for w in work_markers):
        return "work"

    if any(t in text_l for t in task_markers):
        return "task"

    # Default → task (safer)
    return "task"


# =========================================================
# Main
# =========================================================

def main(source: str | None = None):
    """
    Manual interrupt ingestion.

    Architecture:
    - Interrupt → Event (always)
    - Event → classified into Task or Work
    - Engines own creation
    - CF handled by EventEngine
    """

    logger.info("\n📱 Interrupt Logger\n")

    # -----------------------------
    # Source resolution
    # -----------------------------
    if source not in {"whatsapp", "call"}:
        source = input("Source (whatsapp / call): ").strip().lower()

    if source not in {"whatsapp", "call"}:
        logger.error("❌ Invalid source")
        return

    # -----------------------------
    # Summary
    # -----------------------------
    title = input("Interrupt summary (one line): ").strip()
    if not title:
        logger.error("❌ Summary required")
        return

    now = utc_now()

    # =====================================================
    # 1️⃣ REGISTER INTERRUPT EVENT (FACT)
    # =====================================================
    try:
        event = event_engine.register_event(
            event_type="interrupt.logged",
            occurred_at=now,
            payload={
                "title": title,
                "source": f"interrupt.{source}",
                "unplanned": True,
            },
        )
        interrupt_col.insert_one(event)
    except Exception:
        logger.exception("❌ Failed to register interrupt event")
        return

    event_id = event["event_id"]

    # =====================================================
    # 2️⃣ CLASSIFY INTERRUPT
    # =====================================================
    kind = classify_interrupt(title)

    # =====================================================
    # 3️⃣ DELEGATE TO ENGINE
    # =====================================================
    try:
        if kind == "task":
            task = task_engine.create_task(
                title=title,
                source=f"interrupt.{source}",
                source_event_id=event_id,
                occurred_at=now,
                signals={
                    "unplanned": True,
                    "interrupt": True,
                },
            )

            logger.info("📌 Classified as TASK")
            logger.info("🧾 Task ID : %s", task["task_id"])

        else:
            work=work_engine.record_work(
                event_id=event_id,
                title=title,
                started_at=now,
                ended_at=now + timedelta(minutes=5),
                source="interrupt.call",
                work_type="interrupt",
            )

            logger.info("📌 Classified as WORK")
            logger.info("🧾 Work ID : %s", work["work_id","None"])

    except Exception:
        logger.exception("❌ Failed to apply interrupt classification")

    # =====================================================
    # Feedback
    # =====================================================
    logger.info("✅ Interrupt processed successfully")
    logger.info("📌 Event ID : %s", event_id)


# =========================================================

if __name__ == "__main__":
    main()
