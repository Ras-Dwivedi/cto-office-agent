import uuid
from datetime import datetime

from src.agents.task_manager.utils.cf_engine import process_event
from src.db import get_collection


def main(source=None):
    print("\n📱 Manual Event Ingestion (Interrupt-driven work)\n")

    if source not in {"whatsapp", "call"}:
        source = input("Source (whatsapp / call): ").strip().lower()

    if source not in {"whatsapp", "call"}:
        print("❌ Invalid source")
        return

    text = input("Event summary (one line): ").strip()
    if not text:
        print("❌ Summary required")
        return

    now = datetime.utcnow()

    # 🔑 Unified event type
    event_type = "interrupt"
    event_id = f"INT-{uuid.uuid4().hex[:8]}"

    # ----------------------------------------
    # Store raw interrupt event (fact)
    # ----------------------------------------
    events_col = get_collection("raw_events")
    events_col.insert_one({
        "event_id": event_id,
        "event_type": event_type,   # unified
        "source": source,           # whatsapp | call
        "text": text,
        "timestamp": now
    })

    # ----------------------------------------
    # Send to CF engine
    # ----------------------------------------
    process_event(
        event_id=event_id,
        event_type=event_type,
        event_text=text,
        now=now
    )

    print("\n✅ Interrupt event recorded and context inferred")
    print(f"📌 Source: {source}")


if __name__ == "__main__":
    main()
