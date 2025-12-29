from datetime import datetime

from dateutil.parser import parse


def compute_priority(task):
    """
    Returns:
        int priority score (higher = more important)
        OR None if task should not be considered today
    """

    score = 0
    now = datetime.now()

    # -------------------------
    # 1. HARD EXCLUSIONS
    # -------------------------

    # Expired tasks → no priority today
    due_by = task.get("due_by")
    if due_by:
        try:
            if parse(due_by) < now:
                return None
        except Exception:
            pass

    # Stale tasks → deprioritize unless revived
    created_at = task.get("created_at")
    last_activity = task.get("last_activity_at")

    try:
        created_time = parse(created_at) if created_at else None
        last_activity_time = parse(last_activity) if last_activity else None
    except Exception:
        created_time = None
        last_activity_time = None

    if created_time:
        age_days = (now - created_time).days

        # Older than 30 days AND no recent activity → ignore
        if age_days > 30:
            if not last_activity_time or (now - last_activity_time).days > 7:
                return None

    # -------------------------
    # 2. DEADLINE URGENCY
    # -------------------------

    if due_by:
        try:
            days_left = (parse(due_by) - now).days

            if days_left <= 1:
                score += 5
            elif days_left <= 3:
                score += 3
            elif days_left <= 7:
                score += 1
        except Exception:
            pass

    # -------------------------
    # 3. STRATEGIC IMPORTANCE
    # -------------------------

    if task.get("institutional"):
        score += 4

    if task.get("blocks_others"):
        score += 3

    if task.get("external_dependency"):
        score += 2

    # -------------------------
    # 4. STAKEHOLDER WEIGHT
    # -------------------------

    stakeholder = task.get("stakeholder")
    if stakeholder in ["CEO", "Chairman"]:
        score += 3
    elif stakeholder:
        score += 1

    # -------------------------
    # 5. DELEGATION PENALTY
    # -------------------------

    if task.get("delegatable"):
        score -= 1

    # -------------------------
    # 6. FLOOR & RETURN
    # -------------------------

    # If score never crossed meaningful threshold, ignore
    if score <= 0:
        return None

    return score
