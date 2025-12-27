from datetime import datetime
from src.db import get_collection

# ---------------- Config ----------------

OUTPUT_DIR = "exports"
COLLECTION_NAME = "decisions"

FIELD_ORDER = [
    "decision",
    "context",
    "assumptions",
    "expected_outcome",
    "review_date",
    "what_i_learned"
]

# ---------------- Helpers ----------------

def titleize(field: str) -> str:
    return field.replace("_", " ").title()

# ---------------- Main ----------------

def main():
    decisions_col = get_collection(COLLECTION_NAME)

    decisions = decisions_col.find().sort("timestamp", 1)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    output_file = f"{OUTPUT_DIR}/decision-log-{timestamp}.md"

    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Decision Log\n\n")

        for d in decisions:
            ts = d["timestamp"].isoformat(timespec="minutes")
            f.write(f"## Decision Log – {ts}\n\n")

            for field in FIELD_ORDER:
                value = d.get(field)
                if value:
                    f.write(f"**{titleize(field)}:**\n{value}\n\n")

            f.write("---\n\n")

    print(f"\n✅ Markdown generated: {output_file}")

if __name__ == "__main__":
    main()
