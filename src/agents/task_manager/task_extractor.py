import requests
import json
import logging
from datetime import datetime

from src.config.config import OLLAMA_URL, OLLAMA_MODEL
from src.db import get_collection

from src.agents.task_manager.utils.project_resolver import resolve_project_id
from src.agents.task_manager.utils.task_id import generate_task_id
from src.agents.task_manager.utils.verb_resolver import resolve_task_verb  # you should have / add this

logger = logging.getLogger(__name__)

tasks_col = get_collection("tasks")


def store_task(task):
    """
    Store a task with required metadata for downstream agents.
    NOTE: This assumes idempotency / upsert may be added later.
    """
    now = datetime.utcnow().isoformat()

    task.setdefault("created_at", now)
    task["last_activity_at"] = now
    task.setdefault("status", "OPEN")

    tasks_col.insert_one(task)


def extract_tasks(email):
    """
    Extract actionable tasks from an email using Ollama.

    Responsibilities:
    - Call LLM for task extraction ONLY
    - Enrich tasks with deterministic metadata
    - Store tasks
    """

    prompt = f"""
You are assisting Ras Dwivedi, CTO of C3I Hub.

Owner:
- Person or team responsible for completing the task.

Institutional task:
- true if the task:
  - creates or improves SOPs, policies, workflows, governance
  - reduces repeated manual decisions
  - has long-term organizational impact
- false otherwise

Examples:
- "Define SOC alert resolution SOP" → institutional = true
- "Share meeting link" → institutional = false

Extract ACTIONABLE TASKS from the email below.
If no actionable task exists, return EMPTY.

Return STRICT JSON array only:
[
  {{
    "title": "...",
    "owner": "...",
    "due_by": "YYYY-MM-DD or null",
    "institutional": true/false,
    "blocks_others": true/false,
    "external_dependency": true/false,
    "delegatable": true/false
  }}
]

Email:
Subject: {email['subject']}
Body:
{email['body']}
"""

    # ---------------- LLM call ----------------
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
    except Exception:
        logger.exception("Failed to call Ollama API")
        raise RuntimeError("Ollama API call failed")

    if response.status_code != 200:
        logger.error("Ollama HTTP error: %s", response.text)
        raise RuntimeError(response.text)

    try:
        data = response.json()
    except Exception:
        logger.error("Ollama returned non-JSON response: %s", response.text)
        raise RuntimeError("Invalid Ollama response")

    # ---------------- Response parsing ----------------
    if "error" in data:
        logger.error("Ollama error: %s", data["error"])
        raise RuntimeError(data["error"])

    if "response" in data:
        text = data["response"]
    elif "message" in data and "content" in data["message"]:
        text = data["message"]["content"]
    else:
        logger.error("Unexpected Ollama response format: %s", data)
        raise RuntimeError("Unexpected Ollama response format")

    if not text or "EMPTY" in text:
        return []

    try:
        tasks = json.loads(text)
    except Exception:
        logger.error("Failed to parse task JSON from LLM output:\n%s", text)
        raise RuntimeError("Invalid task JSON")

    # ---------------- Enrich + store tasks ----------------
    for task in tasks:
        # ---- Email provenance (SOURCE OF TRUTH) ----
        task["email_uid"] = email.get("uid")
        task["email_subject"] = email.get("subject")
        task["email_from"] = email.get("from")
        task["source"] = "email"

        # ---- Project resolution (deterministic) ----
        task["project_id"] = resolve_project_id(task)

        # ---- Verb resolution (deterministic) ----
        task["task_verb"] = resolve_task_verb(task)

        # ---- Deterministic task identity ----
        task["task_id"] = generate_task_id(
            project_id=task["project_id"],
            verb=task["task_verb"],
            title=task["title"]
        )

        store_task(task)

    logger.info(
        "Extracted and stored %d task(s) from email UID=%s",
        len(tasks),
        email.get("uid")
    )

    return tasks
