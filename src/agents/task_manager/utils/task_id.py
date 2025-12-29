import hashlib


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def deterministic_hash(text: str, length=6) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return h[:length].upper()


def generate_task_id(
    project_id: str,
    verb: str,
    title: str,
    source_event_id: str | None = None,
) -> str:
    """
    Deterministic task ID.

    Identity rules:
    - Same source_event_id → same task
    - Else fallback to normalized title hash
    """

    if source_event_id:
        h = deterministic_hash(source_event_id)
    else:
        h = deterministic_hash(normalize(title))

    return f"TASK::{project_id}::{verb.upper()}::{h}"
