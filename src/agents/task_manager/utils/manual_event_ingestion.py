import uuid
from datetime import datetime

from src.agents.task_manager.utils.cf_engine import process_event
from src.db import get_collection


def main():
    print("\n📱 Manual Event Ingestion (WhatsApp / Call)\n")

    event_type = input("Event type (whatsapp / call): ").strip().lower()
    if event_type not in {"whatsapp", "call"}:
        print("❌ Invalid event type")
        return

    text = input("Event summary (one line): ").strip()
    if not text:
        print("❌ Summary required")
        return

    now = datetime.utcnow()
    event_id = f"{event_type.upper()}-{uuid.uuid4().hex[:8]}"

    # Optional: store raw event (recommended)
    events_col = get_collection("raw_events")
    events_col.insert_one({
        "event_id": event_id,
        "event_type": event_type,
        "text": text,
        "timestamp": now,
        "source": "manual"
    })

    # Send to CF engine
    process_event(
        event_id=event_id,
        event_type=event_type,
        event_text=text,
        now=now
    )

    print("\n✅ Event recorded and context inferred")


if __name__ == "__main__":
    main()
