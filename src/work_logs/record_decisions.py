import sys
from datetime import datetime
from src.db import get_collection

# ---------------- Collections ----------------

decisions_col = get_collection("decisions")

# ---------------- Config ----------------

QUICK_FIELDS = [
    "Decision",
    "Expected Outcome",
    "Review Date"
]

LONG_FIELDS = [
    "Decision",
    "Context",
    "Assumptions",
    "Expected Outcome",
    "Review Date",
    "What I Learned"
]

# ---------------- Helpers ----------------

def prompt(field):
    print(f"\n{field}:")
    return input("> ").strip()

def normalize(key):
    return key.lower().replace(" ", "_")

# ---------------- Main ----------------

def main():
    long_mode = "--long" in sys.argv
    fields = LONG_FIELDS if long_mode else QUICK_FIELDS
    mode = "LONG" if long_mode else "QUICK"

    now = datetime.now()
    decision_id = now.isoformat(timespec="minutes")

    print(f"\n📝 Recording {mode} decision\n")

    # Base document (single source of truth)
    doc = {
        "decision_id": decision_id,
        "timestamp": now,
        "mode": mode,
        "source": "decision-cli",
        "version": 1,
        "decision": None,
        "context": None,
        "assumptions": None,
        "expected_outcome": None,
        "review_date": None,
        "what_i_learned": None
    }

    # Collect user input
    for field in fields:
        value = prompt(field)
        if value:
            doc[normalize(field)] = value

    # Persist (ONLY via db.py)
    decisions_col.insert_one(doc)

    print("\n✅ Decision stored in MongoDB")

if __name__ == "__main__":
    main()
