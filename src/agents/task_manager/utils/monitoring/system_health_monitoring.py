"""
System Health Monitor
---------------------
Nightly read-only metrics job for CTO Office Agent

- Computes ingestion, semantic, and operational health metrics
- Writes one immutable document per day
- Emits invariant violations as events
"""

import logging
from datetime import datetime, timedelta, timezone
from collections import Counter

from src.db import get_collection
from src.agents.task_manager.utils.event_engine import event_engine

# ===============================
# CONFIG
# ===============================

LOOKBACK_DAYS = 30
ORPHAN_DAYS = 14

# ===============================
# LOGGING
# ===============================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("system_health_monitor")

# ===============================
# HELPERS
# ===============================

def start_of_day(dt):
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)

def end_of_day(dt):
    return start_of_day(dt) + timedelta(days=1)

# ===============================
# METRIC COMPUTATION
# ===============================

def compute_ingestion_metrics(day_start, day_end):
    emails = get_collection("raw_emails")
    attachments = get_collection("attachments")

    emails_ingested = emails.count_documents({
        "received_at": {"$gte": day_start, "$lt": day_end}
    })

    attachments_ingested = attachments.count_documents({
        "received_at": {"$gte": day_start, "$lt": day_end}
    })

    attachments_parsed = attachments.count_documents({
        "parsed": True,
        "received_at": {"$gte": day_start, "$lt": day_end}
    })

    return {
        "emails_ingested": emails_ingested,
        "attachments_ingested": attachments_ingested,
        "attachments_parsed": attachments_parsed,
        "attachments_failed": attachments_ingested - attachments_parsed,
    }


def compute_event_metrics(day_start, day_end):
    events = get_collection("events")

    cursor = events.aggregate([
        {
            "$match": {
                "occurred_at": {"$gte": day_start, "$lt": day_end}
            }
        },
        {
            "$group": {
                "_id": "$event_type",
                "count": {"$sum": 1}
            }
        }
    ])

    return {doc["_id"]: doc["count"] for doc in cursor}


def compute_semantic_metrics(now):
    contexts = get_collection("contexts")
    tasks = get_collection("tasks")
    pomodoros = get_collection("pomodoros")
    decisions = get_collection("decisions")

    since = now - timedelta(days=LOOKBACK_DAYS)
    orphan_cutoff = now - timedelta(days=ORPHAN_DAYS)

    total_cfs = contexts.count_documents({})
    new_cfs = contexts.count_documents({"created_at": {"$gte": since}})

    # CF reuse
    cf_usage = Counter()

    for col, field in [
        (tasks, "context_id"),
        (pomodoros, "context_id"),
        (decisions, "context_id"),
    ]:
        for doc in col.find({"context_id": {"$ne": None}}, {"context_id": 1}):
            cf_usage[doc["context_id"]] += 1

    reused_cfs = sum(1 for v in cf_usage.values() if v > 1)

    # Orphan CFs
    orphan_cfs = contexts.count_documents({
        "created_at": {"$lt": orphan_cutoff},
        "_id": {"$nin": list(cf_usage.keys())}
    })

    return {
        "total_cfs": total_cfs,
        "new_cfs_last_30d": new_cfs,
        "cf_reuse_ratio": round(reused_cfs / max(total_cfs, 1), 3),
        "orphan_cf_ratio": round(orphan_cfs / max(total_cfs, 1), 3),
    }


def compute_operational_metrics():
    tasks = get_collection("tasks")
    pomodoros = get_collection("pomodoros")
    decisions = get_collection("decisions")

    orphan_tasks = tasks.count_documents({
        "status": {"$ne": "completed"},
        "updated_at": {"$lt": datetime.now(timezone.utc) - timedelta(days=ORPHAN_DAYS)}
    })

    total_tasks = tasks.count_documents({})

    decision_followups = decisions.count_documents({
        "first_followup_at": {"$exists": True}
    })

    total_decisions = decisions.count_documents({})

    return {
        "orphan_task_ratio": round(orphan_tasks / max(total_tasks, 1), 3),
        "decision_followthrough_ratio": round(
            decision_followups / max(total_decisions, 1), 3
        ),
    }


# ===============================
# GUARDRAILS
# ===============================

def check_invariants(metrics):
    violations = []

    if metrics["ingestion"]["attachments_parsed"] > metrics["ingestion"]["attachments_ingested"]:
        violations.append("attachments_parsed_exceeds_ingested")

    if metrics["ingestion"]["emails_ingested"] < metrics["events"].get("task.created", 0):
        violations.append("tasks_exceed_emails")

    return violations


# ===============================
# MAIN
# ===============================

def main():
    logger.info("Starting system health monitoring job")

    now = datetime.now(timezone.utc)
    day_start = start_of_day(now - timedelta(days=1))
    day_end = end_of_day(now - timedelta(days=1))

    metrics = {
        "date": day_start.date().isoformat(),
        "computed_at": now,
        "ingestion": compute_ingestion_metrics(day_start, day_end),
        "events": compute_event_metrics(day_start, day_end),
        "semantic": compute_semantic_metrics(now),
        "operational": compute_operational_metrics(),
    }

    violations = check_invariants(metrics)

    metrics["invariants"] = {
        "violations": violations,
        "healthy": len(violations) == 0
    }

    get_collection("system_metrics").insert_one(metrics)

    for v in violations:
        event_engine.register_event(
            event_type="system.invariant_violation",
            occurred_at=now,
            payload={
                "violation": v,
                "date": metrics["date"]
            }
        )

    logger.info("System health metrics recorded successfully")


if __name__ == "__main__":
    main()
