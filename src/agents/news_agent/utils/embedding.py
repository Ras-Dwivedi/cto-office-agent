# src/llm/embedding.py

import requests
from functools import lru_cache
from typing import List

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"


@lru_cache(maxsize=4096)
def embed_text(text: str) -> List[float]:
    """
    Generate embeddings using Ollama.
    Cached for CF reuse.
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")

    payload = {
        "model": EMBEDDING_MODEL,
        "prompt": text.strip()
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=60)
    response.raise_for_status()

    data = response.json()

    if "embedding" not in data:
        raise RuntimeError(f"Ollama embedding failed: {data}")

    return data["embedding"]
