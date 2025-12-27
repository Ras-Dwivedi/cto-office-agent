from datetime import datetime, timedelta
from src.db import get_collection

tasks_col = get_collection("tasks")
edges_col = get_collection("event_cf_edges")
contexts_col = get_collection("context_fingerprints")


# -----------------------------
# Tunable weights (keep simple)
# -----------------------------

INTERRUPT_WEIGHT = 1.5
DECISION_WEIGHT = 1.3
BUSINESS_WEIGHT = 1.4
RECENT_ACTIVITY_DAYS = 3


def compute_cf_priority_boost(task_id):
    """
    Compute a priority boost based on CF signals.
    """
    if task_id is None:
        return 1.0

    boost = 1.0
    now = datetime.utcnow()
    recent_cutoff = now - timedelta(days=RECENT_ACTIVITY_DAYS)

    # Find CFs linked to this task
    edges = list(edges_col.find(
        {
            "event_id": f"TASK-{task_id}"
        },
        {"_id": 0, "cf_id": 1}
    ))

    if not edges:
        return boost

    cf_ids = [e["cf_id"] for e in edges]

    for cf in contexts_col.find({"cf_id": {"$in": cf_ids}}):
        # 🔹 Recency boost
        if cf.get("last_activity") and cf["last_activity"] >= recent_cutoff:
            boost *= 1.2

        stats = cf.get("stats", {})

        # 🔹 Interrupt-heavy CF
        if stats.get("by_event_type", {}).get("interrupt", 0) > 0:
            boost *= INTERRUPT_WEIGHT

        # 🔹 Decision-heavy CF
        if stats.get("by_event_type", {}).get("decision", 0) > 0:
            boost *= DECISION_WEIGHT

        # 🔹 Business facet boost
        facets = cf.get("facets", {})
        business_score = (
            facets.get("domain", {}).get("business_dev", 0) +
            facets.get("orientation", {}).get("business", 0)
        )

        if business_score > 0:
            boost *= BUSINESS_WEIGHT

    return round(boost, 2)


def get_top_priority_tasks(limit=5):
    """
    Fetch tasks and compute effective priority dynamically.
    """

    tasks = list(tasks_col.find(
        {"status": "OPEN"},
        {
            "_id": 0,
            "task_id": 1,
            "title": 1,
            "priority_score": 1,
            "stakeholder": 1,
            "project_id": 1,
            "task_verb": 1,
        }
    ))

    for t in tasks:
        try:
            base = t.get("priority_score", 1.0)
            boost = compute_cf_priority_boost(t["task_id"])
            t["effective_priority"] = round(base * boost, 2)
        except Exception:
            t["effective_priority"] = 1.00

    tasks.sort(key=lambda x: x["effective_priority"], reverse=True)
    return tasks[:limit]


def get_priority_task():
    tasks = get_top_priority_tasks()

    print("\n🔥 TOP PRIORITY TASKS FOR TODAY (Context-Aware)\n")

    if not tasks:
        print("(No open priority tasks)")
        return

    for i, t in enumerate(tasks, 1):
        print(f"{i}. {t['title']}")
        print(f"   🆔 Task ID   : {t.get('task_id')}")
        print(f"   ⭐ Priority  : {t.get('effective_priority')}")
        print(f"   👤 Stakeholder : {t.get('stakeholder')}")
        print(f"   📁 Project  : {t.get('project_id')} | Verb: {t.get('task_verb')}")
        print()
