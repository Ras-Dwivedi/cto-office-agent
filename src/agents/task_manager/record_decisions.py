import sys
import hashlib
from datetime import datetime

from src.db import get_collection

# ---------------- Collections ----------------

decisions_col = get_collection("decisions")

# ---------------- Config ----------------
# QUICK decisions ALSO capture context (important for institutional memory)

QUICK_FIELDS = [
    "Decision",
    "Context",
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


def context_fingerprint(*parts):
    """
    Generate a deterministic fingerprint from decision context.
    Used to detect repeated / similar decisions later.
    """
    text = "||".join(
        p.strip().lower()
        for p in parts
        if p
    )

    if not text:
        return None

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"CTX-{digest[:8].upper()}"


# ---------------- Main ----------------

def main():
    long_mode = "--long" in sys.argv
    fields = LONG_FIELDS if long_mode else QUICK_FIELDS
    mode = "LONG" if long_mode else "QUICK"

    now = datetime.utcnow()
    decision_id = now.isoformat(timespec="minutes")

    print(f"\n📝 Recording {mode} decision\n")

    # Canonical decision document
    doc = {
        "decision_id": decision_id,
        "timestamp": now,
        "mode": mode,
        "source": "decision-cli",
        "version": 1,

        # Core fields
        "decision": None,
        "context": None,
        "assumptions": None,
        "expected_outcome": None,
        "review_date": None,
        "what_i_learned": None,

        # Derived
        "context_fingerprint": None
    }

    # Collect user input
    for field in fields:
        value = prompt(field)
        if value:
            doc[normalize(field)] = value

    # -------------------------
    # Context fingerprint
    # -------------------------
    doc["context_fingerprint"] = context_fingerprint(
        doc.get("decision"),
        doc.get("context"),
        doc.get("assumptions")
    )

    # Persist
    decisions_col.insert_one(doc)

    print("\n✅ Decision stored in MongoDB")
    if doc["context_fingerprint"]:
        print(f"🔑 Context fingerprint: {doc['context_fingerprint']}")


if __name__ == "__main__":
    main()
