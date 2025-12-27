import hashlib


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def deterministic_hash(text: str, length=6) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return h[:length].upper()


def generate_task_id(project_id: str, verb: str, title: str) -> str:
    """
    Deterministic task ID based on project + verb + task title.
    """
    normalized_title = normalize(title)
    h = deterministic_hash(normalized_title)
    return f"TASK::{project_id}::{verb.upper()}::{h}"
