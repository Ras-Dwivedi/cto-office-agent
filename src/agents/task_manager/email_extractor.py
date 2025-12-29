import json
import logging
from datetime import datetime

import requests

from src.agents.task_manager.utils.project_resolver import resolve_project_id
from src.agents.task_manager.utils.verb_resolver import resolve_task_verb
from src.config.config import OLLAMA_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


def extract_tasks(email):
    """
    Extract actionable tasks from an email using Ollama.

    Responsibilities:
    - Call LLM for task extraction ONLY
    - Enrich tasks with deterministic metadata
    - NEVER generate task_id
    - NEVER write to DB
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
Subject: {email.get('subject')}
Body:
{email.get('body')}
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

    now = datetime.utcnow().isoformat()

    # ---------------- Enrich tasks (NO IDENTITY) ----------------
    for task in tasks:
        # ---- Safety: never trust LLM for identity ----
        task.pop("task_id", None)

        # ---- Email provenance ----
        task["email_uid"] = email.get("uid")
        task["email_subject"] = email.get("subject")
        task["email_from"] = email.get("from")
        task["source"] = "email"

        # ---- Deterministic enrichment ----
        task["project_id"] = resolve_project_id(task)
        task["task_verb"] = resolve_task_verb(task)

        # ---- Timestamps (non-identity) ----
        task.setdefault("created_at", now)
        task["last_activity_at"] = now
        task.setdefault("status", "OPEN")

    logger.info(
        "Extracted %d task(s) from email UID=%s",
        len(tasks),
        email.get("uid")
    )

    return tasks

def extract_decisions(email):
    """
    Extract DECISIONS from an email using Ollama.

    Responsibilities:
    - Detect explicit or implicit decisions
    - Return structured decision facts
    - NEVER generate decision_id
    - NEVER write to DB
    """

    prompt = f"""
You are assisting Ras Dwivedi, CTO of C3I Hub.

A DECISION is:
- An approval, rejection, final choice, or commitment
- A conclusion that closes alternatives
- A statement that changes direction, policy, or responsibility

Examples of decisions:
- "Approved the SOC architecture"
- "We will proceed with Vendor A"
- "Decision: Use Kubernetes for deployment"
- "This will NOT be pursued further"

NOT decisions:
- Requests
- Suggestions
- Open discussions
- Tasks or to-dos

Extract DECISIONS from the email below.
If no decision exists, return EMPTY.

Return STRICT JSON array only:
[
  {{
    "decision": "...",
    "context": "...",
    "confidence": "high | medium | low",
    "reversible": true/false,
    "effective_date": "YYYY-MM-DD or null"
  }}
]

Email:
Subject: {email.get('subject')}
Body:
{email.get('body')}
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
        logger.exception("Failed to call Ollama API for decision extraction")
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
        decisions = json.loads(text)
    except Exception:
        logger.error("Failed to parse decision JSON from LLM output:\n%s", text)
        raise RuntimeError("Invalid decision JSON")

    now = datetime.utcnow().isoformat()

    # ---------------- Enrich decisions (NO IDENTITY) ----------------
    for d in decisions:
        # ---- Safety: never trust LLM for identity ----
        d.pop("decision_id", None)

        # ---- Email provenance ----
        d["email_uid"] = email.get("uid")
        d["email_subject"] = email.get("subject")
        d["email_from"] = email.get("from")
        d["source"] = "email"

        # ---- Timestamps ----
        d.setdefault("occurred_at", now)
        d["ingested_at"] = now

    logger.info(
        "Extracted %d decision(s) from email UID=%s",
        len(decisions),
        email.get("uid")
    )

    return decisions
