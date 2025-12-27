from datetime import datetime, timedelta
from dateutil.parser import parse


def compute_priority(task):
    """
    Returns:
    - None → task should NOT be treated as priority
    - Integer score → higher = more important
    """

    # ---------- HARD DEPRIORITIZATION ----------
    if is_expired(task):
        return None

    if is_stale_without_activity(task):
        return None

    score = 0

    # ---------- STRATEGIC WEIGHT ----------
    if task.get("institutional"):
        score += 6   # Very high leverage

    # ---------- OPERATIONAL WEIGHT ----------
    if task.get("blocks_others"):
        score += 3

    if task.get("external_dependency"):
        score += 2

    if task.get("stakeholder") in ["CEO", "Chairman"]:
        score += 2

    # ---------- TIME PRESSURE ----------
    if task.get("due_by"):
        days = (parse(task["due_by"]) - datetime.now()).days
        if days <= 2:
            score += 3
        elif days <= 5:
            score += 1

    # ---------- DELEGATION PENALTY ----------
    if task.get("delegatable"):
        score -= 1

    return score
