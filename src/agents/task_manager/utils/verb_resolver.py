def resolve_task_verb(task):
    """
    Determine the verb describing how this task relates to its project.

    Rules are deterministic and conservative.
    LLMs are NOT used here.

    Returns:
        str: one of {dev, ops, governance, business, research, hiring, admin}
    """

    title = (task.get("title") or "").lower()
    institutional = task.get("institutional", False)
    delegatable = task.get("delegatable", False)

    # -------------------------
    # 1. Governance / institutional
    # -------------------------
    if institutional:
        return "governance"

    # -------------------------
    # 2. Hiring
    # -------------------------
    hiring_keywords = [
        "hire", "hiring", "recruit", "interview",
        "onboard", "onboarding", "jd", "job description"
    ]
    if any(k in title for k in hiring_keywords):
        return "hiring"

    # -------------------------
    # 3. Research / academic
    # -------------------------
    research_keywords = [
        "research", "paper", "publication", "survey",
        "experiment", "analysis", "proposal", "grant"
    ]
    if any(k in title for k in research_keywords):
        return "research"

    # -------------------------
    # 4. Business / external
    # -------------------------
    business_keywords = [
        "proposal", "client", "meeting", "moU", "mou",
        "partnership", "collaboration", "funding", "tender"
    ]
    if any(k in title for k in business_keywords):
        return "business"

    # -------------------------
    # 5. Operations / execution
    # -------------------------
    ops_keywords = [
        "deploy", "setup", "configure", "install",
        "procure", "purchase", "fix", "resolve",
        "monitor", "arrange", "coordinate", "ensure"
    ]
    if any(k in title for k in ops_keywords):
        return "ops"

    # -------------------------
    # 6. Development / engineering
    # -------------------------
    dev_keywords = [
        "develop", "implement", "build", "code",
        "design", "integrate", "automate"
    ]
    if any(k in title for k in dev_keywords):
        return "dev"

    # -------------------------
    # 7. Admin (safe fallback)
    # -------------------------
    if delegatable:
        return "admin"

    # -------------------------
    # 8. Default fallback
    # -------------------------
    return "ops"
