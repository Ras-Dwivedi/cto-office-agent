import hashlib
from datetime import datetime
import math
from typing import List

def hash_url(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()

def now():
    return datetime.utcnow()
# src/math/similarity.py



def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    Returns value in [-1, 1]
    """
    if not vec1 or not vec2:
        raise ValueError("Vectors must not be empty")

    if len(vec1) != len(vec2):
        raise ValueError("Vectors must be of same dimension")

    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot / (norm1 * norm2)
