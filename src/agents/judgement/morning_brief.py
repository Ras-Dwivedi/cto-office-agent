from datetime import datetime

from dateutil.parser import parse

from src.db import get_collection

tasks_col = get_collection("tasks")

DELEGATE_MAX_AGE_DAYS = 7


# -------------------------
# Helpers
# -------------------------

def _days_to_due(task):
    if not task.get("due_by"):
        return None
    try:
        return (parse(task["due_by"]) - datetime.utcnow()).days
    except Exception:
        return None


def _task_age_days(task):
    try:
        created = parse(task["created_at"])
        return (datetime.utcnow() - created).days
    except Exception:
        return None


def _email_context(task):
    """
    Return formatted email sender, subject, and date for awareness & traceability.
    """
    # Sender
    sender = task.get("email_from")
    sender_str = None

    if isinstance(sender, list) and sender:
        sender_str = sender[0][0] or sender[0][1]
    elif isinstance(sender, str):
        sender_str = sender

    # Subject
    subject = task.get("email_subject", "No subject")

    # Date (best available)
    try:
        email_date = parse(task["created_at"]).strftime("%d %b %Y")
    except Exception:
        email_date = "unknown date"

    parts = []
    if sender_str:
        parts.append(f"From: {sender_str}")
    parts.append(f"Date: {email_date}")
    parts.append(f"Subject: {subject}")

    return "📧 " + " | ".join(parts)


def get_open_tasks():
    return list(tasks_col.find({"status": "OPEN"}))


# -------------------------
# Core classification logic
# -------------------------

def classify_tasks(tasks):
    delegate = []
    personal = []

    for task in tasks:
        days_left = _days_to_due(task)
        age_days = _task_age_days(task)

        # ---------- Delegate-first logic ----------
        if (
            task.get("delegatable") is True
            and not task.get("institutional")
            and task.get("task_verb") not in ["governance", "research"]
            and task.get("owner") not in ["Ras Dwivedi"]
            and (days_left is None or days_left > 1)
            and (age_days is None or age_days <= DELEGATE_MAX_AGE_DAYS)
        ):
            delegate.append(task)
            continue

        # ---------- Personal-focus logic ----------
        if (
            task.get("institutional") is True
            or task.get("blocks_others") is True
            or task.get("delegatable") is False
            or (days_left is not None and days_left <= 3)
        ):
            personal.append(task)

    return delegate, personal


# -------------------------
# Scoring & explanation
# -------------------------

def score_personal_task(task):
    score = 0

    if task.get("institutional"):
        score += 4

    if task.get("blocks_others"):
        score += 3

    days_left = _days_to_due(task)
    if days_left is not None:
        if days_left <= 1:
            score += 4
        elif days_left <= 3:
            score += 2

    if task.get("stakeholder") in ["CEO", "Chairman"]:
        score += 3

    return score


def generate_reason(task, category):
    if category == "delegate":
        return "Delegatable execution task with no institutional or strategic dependency."

    reasons = []
    if task.get("institutional"):
        reasons.append("institutional impact")
    if task.get("blocks_others"):
        reasons.append("blocks others")
    if task.get("delegatable") is False:
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

    personal_scored = [
        (score_personal_task(t), t) for t in personal
    ]
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
            print(f"  {_email_context(t)}")
            print(f"  Reason: {generate_reason(t, 'delegate')}\n")

    print("\n🧠 FOCUS YOURSELF (TOP 5):\n")
    if not personal_top:
        print("  (No critical personal-focus tasks)\n")
    else:
        for i, t in enumerate(personal_top, 1):
            print(f"{i}. {t['title']}")
            print(f"   Project: {t.get('project_id')} | Verb: {t.get('task_verb')}")
            print(f"   {_email_context(t)}")
            print(f"   Reason: {generate_reason(t, 'personal')}\n")
