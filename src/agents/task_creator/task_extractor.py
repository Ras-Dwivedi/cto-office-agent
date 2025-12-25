import requests
import json
import logging
from datetime import datetime

from src.config import OLLAMA_URL, OLLAMA_MODEL
from src.db import get_collection

logger = logging.getLogger(__name__)

tasks_col = get_collection("tasks")


def store_task(task):
    """
    Store a task with required metadata for downstream agents.
    """
    now = datetime.utcnow().isoformat()

    task["created_at"] = now
    task["last_activity_at"] = now
    task["status"] = "OPEN"

    tasks_col.insert_one(task)


def extract_tasks(email):
    """
    Extract actionable tasks from an email using Ollama.
    This function is responsible ONLY for clean task extraction
    and metadata enrichment — NOT prioritization.
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
    except Exception as e:
        logger.error("Failed to call Ollama API", exc_info=True)
        raise RuntimeError(str(e))

    if response.status_code != 200:
        logger.error("Ollama HTTP error: %s", response.text)
        raise RuntimeError(response.text)

    try:
        data = response.json()
    except Exception:
        logger.error("Ollama returned non-JSON response: %s", response.text)
        raise RuntimeError("Invalid Ollama response")

    # ---- Robust response parsing ----
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

    # ---- Store tasks with metadata ----
    for task in tasks:
        store_task(task)

    logger.info("Extracted and stored %d task(s) from email UID=%s",
                len(tasks), email.get("uid"))

    return tasks
