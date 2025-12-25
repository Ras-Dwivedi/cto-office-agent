import requests
import json
from config import OLLAMA_URL, OLLAMA_MODEL
from db import get_collection
import logging
logger = logging.getLogger(__name__)


tasks_col = get_collection("tasks")

def store_task(task):
    tasks_col.insert_one(task)


def extract_tasks(email):
    prompt = f"""
I, Ras Dwivedi, is CTO of C3I hub. 
Owner of the task is one who is responsible to complete it. 
Stake holder are the people interested in the task. probably from following: 
    1. Ras Dwivedi
    2. SOC Team
    3. Blockchain Team
    4. VAPT Team
    5. ISMS Team
    6. HR Team
    7. External party
    8. C3I Hub Internal
    9. Any other person who is interested in the task
    
    if stakeholder is ambiguous: make None as the stakeholder
    usually stakeholders are people to whom email is sent.
Extract ACTIONABLE TASKS from this email.
If none exist, return EMPTY.

Return STRICT JSON array:
[
 {{
  "title": "...",
  "owner": "...",
  "stakeholder": "...",
  "due_by": "YYYY-MM-DD or null",
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

    r = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    )

    try:
        data = r.json()
    except Exception as e:
        logger.error(f"Failed to extract tasks: {e}")
        raise RuntimeError(f"Ollama returned non-JSON response: {r.text}")

    # print("🔍 Ollama raw response:", data)

    if "response" not in data:
        raise RuntimeError(f"Ollama response missing 'response' key: {data}")

    text = data["response"]

    if "EMPTY" in text:
        return []

    return json.loads(text)
