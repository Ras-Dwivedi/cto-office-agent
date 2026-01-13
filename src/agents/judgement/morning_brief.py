from datetime import datetime, timezone

from dateutil.parser import parse

from src.agents.utils.logger import logger
from src.db import get_collection

tasks_col = get_collection("tasks")

DELEGATE_MAX_AGE_DAYS = 7


# -------------------------
# Helpers
# -------------------------

def _signals(task):
    return task.get("signals", {}) or {}


def _days_to_due(task):
    due_by = _signals(task).get("due_by")
    if not due_by:
        return None

    try:
        if isinstance(due_by, datetime):
            due = due_by
        elif isinstance(due_by, str):
            due = parse(due_by)
        else:
            return None

        # Timezone-safe comparison
        if due.tzinfo is not None:
            now = datetime.now(timezone.utc)
        else:
            now = datetime.utcnow()

        return (due - now).days

    except Exception:
        logger.error("Failed to compute days_to_due", exc_info=True)
        logger.error(due_by)
        return None


def _task_age_days(task):
    try:
        created_at = task.get("created_at")

        if created_at is None:
            return None

        # Case 1: MongoDB / PyMongo datetime
        if isinstance(created_at, datetime):
            created = created_at

        # Case 2: string (legacy / external)
        elif isinstance(created_at, str):
            created = parse(created_at)

        else:
            raise TypeError(f"Unsupported type for created_at: {type(created_at)}")

        # Normalize timezone
        if created.tzinfo is not None:
            now = datetime.now(timezone.utc)
        else:
            now = datetime.utcnow()

        return (now - created).days

    except Exception:
        logger.error("Failed to parse task creation date", exc_info=True)
        logger.error(task.get("created_at"))
        return None

def _task_context(task):
    """
    Return compact source-aware context line.
    """
    source = task.get("source", "unknown")

    created_at = task.get("created_at")
    created_str = "unknown date"

    try:
        if isinstance(created_at, datetime):
            created = created_at
        elif isinstance(created_at, str):
            created = parse(created_at)
        else:
            created = None

        if created:
            created_str = created.strftime("%d %b %Y")

    except Exception:
        logger.error("Failed to format task creation date", exc_info=True)
        logger.error(created_at)

    return f"📌 Source: {source} | Created: {created_str}"

def _days_since_activity(task):
    last = task.get("last_activity_at")
    if not last:
        return None

    if isinstance(last, datetime):
        ref = last
    elif isinstance(last, str):
        ref = parse(last)
    else:
        return None

    now = datetime.utcnow()
    return (now - ref).days


def get_open_tasks():
    return list(tasks_col.find({"status": "OPEN"}))


# -------------------------
# Core classification logic
# -------------------------

def classify_tasks(tasks):
    delegate = []
    personal = []

    for task in tasks:
        signals = _signals(task)
        days_left = _days_to_due(task)
        age_days = _task_age_days(task)

        # ---------- Delegate-first logic ----------
        can_delegate = (
            signals.get("delegatable") is True
            and not signals.get("institutional")
            and task.get("task_verb") not in ["governance", "research"]
            and age_days is not None
            and age_days <= DELEGATE_MAX_AGE_DAYS
            and (
                days_left is None          # no deadline → rely on age
                or days_left > 1           # has deadline → must be safe
            )
        )

        if can_delegate:
            delegate.append(task)
            continue

        # ---------- Personal-focus logic ----------
        must_personal = (
            signals.get("institutional") is True
            or signals.get("blocks_others") is True
            or signals.get("delegatable") is False
            or (days_left is not None and days_left <= 3)
        )

        if must_personal:
            personal.append(task)

    return delegate, personal
# -------------------------
# Scoring & explanation
# -------------------------

def score_personal_task(task):
    score = 0
    signals = _signals(task)

    # 1. Institutional risk
    if signals.get("institutional"):
        score += 60

    # 2. Blocking others
    if signals.get("blocks_others"):
        score += 50

    # 3. Deadline pressure
    days_left = _days_to_due(task)
    if days_left is not None:
        if days_left <= 0:
            score += 100
        elif days_left <= 1:
            score += 80
        elif days_left <= 3:
            score += 50
        elif days_left <= 7:
            score += 25

    # 4. Reactivation signal (NOT age)
    inactive_days = _days_since_activity(task)
    if inactive_days is not None:
        if inactive_days <= 1:
            score += 30      # just resurfaced
        elif inactive_days <= 3:
            score += 20
        elif inactive_days <= 7:
            score += 15
        # elif inactive_days <= 30:
        #     score += 10
        else:
            score = 0
        # >7 days → no boost

    return score

def generate_reason(task, category):
    signals = _signals(task)

    if category == "delegate":
        return "Delegatable task with no institutional or blocking dependency."

    reasons = []
    if signals.get("institutional"):
        reasons.append("institutional impact")
    if signals.get("blocks_others"):
        reasons.append("blocks others")
    if signals.get("delegatable") is False:
        reasons.append("requires your involvement")

    days_left = _days_to_due(task)
    if days_left is not None and days_left <= 3:
        reasons.append("urgent deadline")

    return ", ".join(reasons) if reasons else "requires direct attention"



# -------------------------
# Public entrypoint
# -------------------------

def morning_judgement_brief():
    tasks = get_open_tasks()
    delegate, personal = classify_tasks(tasks)

    delegate_sorted = sorted(
        delegate,
        key=lambda t: _days_to_due(t) or 999
    )

    personal_scored = [(score_personal_task(t), t) for t in personal]
    personal_top = [
        t for _, t in sorted(
            personal_scored, key=lambda x: x[0], reverse=True
        )[:5]
    ]

    print("\n🌅 MORNING JUDGMENT BRIEF\n")

    print("🧑‍🤝‍🧑 DELEGATE FIRST:\n")
    if not delegate_sorted:
        print("  (No fresh delegatable tasks)\n")
    else:
        for t in delegate_sorted:
            print(f"- {t['title']}")
            print(f"  Project: {t.get('project_id')} | Verb: {t.get('task_verb')}")
            print(f"  {_task_context(t)}")
            print(f"  Reason: {generate_reason(t, 'delegate')}\n")

    print("\n🧠 FOCUS YOURSELF (TOP 5):\n")
    if not personal_top:
        print("  (No critical personal-focus tasks)\n")
    else:
        for i, t in enumerate(personal_top, 1):
            print(f"{i}. {t['title']}")
            print(f"   Project: {t.get('project_id')} | Verb: {t.get('task_verb')}")
            print(f"   {_task_context(t)}")
            print(f"   Reason: {generate_reason(t, 'personal')}\n")
