from src.config.project_registry import load_projects


def resolve_project_id(task):
    """
    Determine the best project_id for a task.

    Rules (deterministic):
    1. If task already has project_id → keep it
    2. Try keyword match against known projects
    3. If ambiguous or no match → UNASSIGNED
    """

    # 1️⃣ Explicit assignment always wins
    if task.get("project_id"):
        return task["project_id"]

    projects = load_projects()

    title = (task.get("title") or "").lower()
    matches = []

    for project_id, meta in projects.items():
        name = meta.get("name", "").lower()
        description = meta.get("description", "").lower()

        if name and name in title:
            matches.append(project_id)
        elif description:
            for word in description.split():
                if len(word) > 4 and word in title:
                    matches.append(project_id)

    # 2️⃣ Exactly one confident match
    if len(matches) == 1:
        return matches[0]

    # 3️⃣ No or multiple matches → unresolved
    return "UNASSIGNED"
