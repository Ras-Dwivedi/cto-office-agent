import re
from collections import defaultdict

from src.agents.task_manager.utils.cf_engine import facet_similarity, _to_utc, CF_LOOKBACK_DAYS
from src.agents.task_manager.utils.cf_facets import FACET_HINTS
from datetime import datetime, timezone
from typing import List, Dict

from src.agents.utils.logger import logger
from src.db import get_collection

contexts_col = get_collection("context_fingerprints")
edges_col = get_collection("event_cf_edges")

def extract_context_fingerprints(query: str) -> Dict[str, Dict[str, float]]:
    """
    Extracts context fingerprints from a user question
    using the SAME semantic model as CF generation.

    Output structure matches CF.facets exactly.
    """
    if not query or not query.strip():
        return {}

    query = query.lower()
    fingerprints: Dict[str, Dict[str, float]] = {}

    for facet, values in FACET_HINTS.items():
        bucket = {}
        for key, keywords in values.items():
            score = 0
            for k in keywords:
                if k in query:
                    score += 1

            if score > 0:
                bucket[key] = float(score)

        if bucket:
            fingerprints[facet] = bucket

    return fingerprints


def get_top_cf_ids(
    query: str,
    limit: int = 10
) -> List[Dict]:
    """
    Returns top CF candidates for a query using
    the SAME semantic model as CF generation.
    """

    if not query or not query.strip():
        return []

    now = datetime.now(timezone.utc)

    # ---- Step 1: Extract query facets (mirror CF engine) ----
    query_facets = extract_context_fingerprints(query)

    results = []

    cursor = contexts_col.find(
        {"status": "active"},
        {
            "cf_id": 1,
            "title": 1,
            "facets": 1,
            "stats.event_count": 1,
            "last_activity": 1
        }
    )

    for cf in cursor:
        cf_facets = cf.get("facets", {})
        if not cf_facets:
            continue

        # ---- Step 2: Facet similarity (PRIMARY) ----
        s_facet = facet_similarity(query_facets, cf_facets)
        if s_facet == 0:
            continue  # hard prune

        # ---- Step 3: Recency score (aligned with CF engine) ----
        last_activity = cf.get("last_activity")
        if last_activity:
            delta = (now - _to_utc(last_activity)).total_seconds()
            s_time = max(0.0, 1 - delta / (CF_LOOKBACK_DAYS * 86400))
        else:
            s_time = 0.0

        # ---- Step 4: Activity signal (weak prior) ----
        event_count = cf.get("stats", {}).get("event_count", 0)
        s_activity = min(event_count / 20, 1.0)

        # ---- Step 5: Final score (same philosophy as cf_confidence) ----
        score = round(
            0.6 * s_facet +
            0.25 * s_time +
            0.15 * s_activity,
            4
        )

        results.append({
            "cf_id": cf["cf_id"],
            "score": score,
            "signals": {
                "facet_similarity": round(s_facet, 4),
                "recency": round(s_time, 4),
                "activity": round(s_activity, 4),
            }
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]

def main():
    """
    Entry point for CF-based context retrieval.
    """

    # ---- Input ----
    query = input("\nEnter your question:\n> ").strip()
    if not query:
        logger.error("Empty query provided")
        return

    # ---- DB ----

    logger.info("Processing query: %s", query)

    # ---- Step 1: Retrieve candidate CFs ----
    results = get_top_cf_ids(
        query=query,
        limit=10
    )

    if not results:
        logger.warning("No relevant CFs found")
        return

    # ---- Output ----
    print("\nTop Context Fingerprints:\n")
    for idx, r in enumerate(results, start=1):
        print(f"{idx}. CF ID: {r['cf_id']}")
        print(f"   Score: {r['score']}")
        print("   Signals:")
        for k, v in r["signals"].items():
            print(f"     - {k}: {v}")
        print()

if __name__ == "__main__":
    main()