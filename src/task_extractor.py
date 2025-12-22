import requests
import json
from .config import OLLAMA_URL, OLLAMA_MODEL

def extract_tasks(email):
    prompt = f"""
You are a CTO Chief-of-Staff AI.

Extract ACTIONABLE TASKS from this email.
If none exist, return EMPTY.

Return STRICT JSON array:
[
 {{
  "title": "...",
  "owner": "...",
  "stakeholder": "CEO | Chairman | Internal | External",
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
        raise RuntimeError(f"Ollama returned non-JSON response: {r.text}")

    print("🔍 Ollama raw response:", data)

    if "response" not in data:
        raise RuntimeError(f"Ollama response missing 'response' key: {data}")

    text = data["response"]

    if "EMPTY" in text:
        return []

    return json.loads(text)
