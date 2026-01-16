import math
import re
from datetime import datetime
from collections import defaultdict

from src.agents.task_manager.task_store import tasks_col
from src.agents.utils.logger import logger
from src.db import get_collection
from src.config.Project_identifiers import PROJECT_KEYWORDS
from src.agents.judgement.utils import MAX_RESULTS, SCORE_THRESHOLD, TIME_DECAY_HOURS, ALL_VERBS, normalize, \
    _extract_text, extract_geography_signals

# -------------------------
# Configuration
# -------------------------


task_col = get_collection("task")
work_col = get_collection("work")
events_col = get_collection("events")
decisions_col = get_collection("decisions")
# -------------------------
# Text utilities
# -------------------------


def extract_verbs(text: str):
    tokens = normalize(text)
    return set(t for t in tokens if t in ALL_VERBS)


def extract_entities(text: str):
    """
    Very cheap entity extractor:
    - Consecutive Capitalized words
    - Acronyms
    """
    return set(re.findall(r"\b[A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]{2,})*", text))

def extract_project_keys(text: str):
    found = set()
    text_lower = text.lower()

    for key, meta in PROJECT_KEYWORDS.items():
        if key.lower() in text_lower:
            found.add(key)
            continue
        for alias in meta.get("aliases", []):
            if alias.lower() in text_lower:
                found.add(key)
                break

    return found

def extract_project_signals(text: str):
    """
    Returns a mapping:
    project -> matched identifiers
    """
    text_l = text.lower()
    matches = {}

    for project, meta in PROJECT_KEYWORDS.items():
        hits = set()

        for alias in meta.get("org_aliases", []):
            if alias.lower() in text_l:
                hits.add(alias)

        for tech in meta.get("tech_keywords", []):
            if tech.lower() in text_l:
                hits.add(tech)

        if hits:
            matches[project] = hits

    return matches

def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def time_proximity(ts, now):
    if not ts:
        return 0.5
    delta_hrs = abs((now - ts).total_seconds()) / 3600
    return math.exp(-delta_hrs / TIME_DECAY_HOURS)


# -------------------------
# Core matcher
# -------------------------

def _extract_timestamp(obj, obj_type):
    if obj_type == "event":
        return obj.get("occurred_at")
    return (
        obj.get("last_activity_at")
        or obj.get("created_at")
    )


def _stable_id(obj, obj_type):
    """
    Return canonical, domain-level stable identity.

    NEVER return MongoDB _id unless absolutely unavoidable.
    """

    if obj_type == "event":
        return obj.get("event_id")

    if obj_type == "task":
        return obj.get("task_id")

    if obj_type == "work":  # pomodoro
        return obj.get("work_id")

    if obj_type == "decision":
        return obj.get("decision_id")

    if obj_type == "interrupt":
        # Interrupts may or may not have a canonical ID
        return obj.get("task_id") or obj.get("interrupt_id")

    # Absolute last-resort fallback (should be logged upstream)
    return None


def _score(sentence, obj, obj_type, now):
    text = _extract_text(obj, obj_type)
    if not text:
        return None

    # -----------------------------
    # Base linguistic signals
    # -----------------------------
    sent_tokens = normalize(sentence)
    sent_verbs = extract_verbs(sentence)
    sent_entities = extract_entities(sentence)

    obj_tokens = normalize(text)
    obj_verbs = extract_verbs(text)
    obj_entities = extract_entities(text)

    bow = jaccard(sent_tokens, obj_tokens)
    verb_match = bool(sent_verbs & obj_verbs)
    entity_overlap = sent_entities & obj_entities

    ts = _extract_timestamp(obj, obj_type)
    tprox = time_proximity(ts, now)

    # -----------------------------
    # Project (org + tech) signals
    # -----------------------------
    sent_projects = extract_project_signals(sentence)
    obj_projects = extract_project_signals(text)

    common_projects = set(sent_projects) & set(obj_projects)

    project_score = 0.0
    project_overlap_detail = {}

    for p in common_projects:
        overlap = sent_projects[p] & obj_projects[p]
        project_overlap_detail[p] = list(overlap)

        # org + tech anchor strength
        project_score += min(len(overlap), 3) * 0.15

    project_score = min(project_score, 0.45)

    # -----------------------------
    # Geography bias (NEW)
    # -----------------------------
    geo_score = 0.0
    geo_detail = {}

    sent_geo = extract_geography_signals(sentence, PROJECT_KEYWORDS)
    obj_geo = extract_geography_signals(text, PROJECT_KEYWORDS)

    for p in common_projects:
        s_geo = sent_geo.get(p, set())
        o_geo = obj_geo.get(p, set())

        if not s_geo or not o_geo:
            continue

        common_geo = s_geo & o_geo
        if not common_geo:
            # same project but different geography → mild penalty
            geo_score -= 0.05
            continue

        geo_detail[p] = list(common_geo)

        # city > state bias
        for g in common_geo:
            geo_score += 0.10  # per matching geo token

    # cap geography influence
    geo_score = max(min(geo_score, 0.30), -0.15)

    # -----------------------------
    # Final score
    # -----------------------------
    score = (
        0.30 * bow +
        0.15 * int(verb_match) +
        0.15 * int(bool(entity_overlap)) +
        0.15 * tprox +
        project_score +
        geo_score
    )

    if score < SCORE_THRESHOLD:
        return None

    return {
        "id": _stable_id(obj, obj_type),
        "type": obj_type,
        "match_probability": round(score, 2),
        "signals": {
            "bow_overlap": round(bow, 2),
            "verb_match": verb_match,
            "entity_overlap": list(entity_overlap),
            "project_overlap": project_overlap_detail,
            "geography_overlap": geo_detail,
            "time_proximity": round(tprox, 2),
            "geo_score": round(geo_score, 2),
        },
        "preview": text[:140],
    }


def retrieve_candidates(
    sentence: str,
    limit: int = MAX_RESULTS
):
    """
    Drop-in function.

    Returns top-N task / pomodoro / interrupt / event
    candidates matching the sentence.
    """

    now = datetime.utcnow()
    results = []

    collections = [
        (tasks_col, "task"),
        (work_col, "work"),
        (decisions_col, "decisions"),
        (events_col, "event"),
    ]

    for col, obj_type in collections:
        logger.debug("querying collection {}".format(col))
        logger.debug(f"obj type: {obj_type}")
        cursor = col.find({}, limit=500)  # recall-heavy, cap later if needed
        for obj in cursor:
            scored = _score(sentence, obj, obj_type, now)
            if scored:
                results.append(scored)
            else:
                logger.debug("unable to score {}".format(scored))

    results.sort(key=lambda x: x["match_probability"], reverse=True)
    return results[:limit]

# def _render_match_preview(match, raw_obj):
#     """
#     Human-readable preview depending on object type.
#     This does NOT affect scoring or inference.
#     """
#
#     t = match["type"]
#
#     if t == "event":
#         payload = raw_obj.get("payload", {})
#         return (
#             payload.get("subject")
#             or payload.get("title")
#             or payload.get("task_text")
#             or payload.get("decision")
#             or "<event with no text>"
#         )
#
#     if t == "task":
#         return raw_obj.get("title") or "<task without title>"
#
#     if t == "work":
#         return {"work": raw_obj.get("work_id"),
#                 "title": raw_obj.get("title")}
#         return raw_obj.get("title") or "<work without title>"
#
#     if t == "decision":
#         return raw_obj.get("decision") or "<decision without text>"
#
#     return "<unknown>"


def get_match_for_text(text):
    print("\n🔍 INPUT TEXT:")
    print(text)
    print("-" * 60)

    matches = retrieve_candidates(text)

    if not matches:
        print("❌ No candidates found")
        return

    # for i, m in enumerate(matches, 1):
    #
    #     # raw_obj = m.get("_raw")  # see note below
    #
    #     print(f"\n#{i} MATCH")
    #     print("Type:", m["type"])
    #     print("ID:", m["id"])
    #     print("Probability:", m["match_probability"])
    #     print("Signals:", m["signals"])
    #     print("text:", m["preview"])
    return matches



def main():
    text = input("\nEnter your question:\n> ").strip()
    if not text:
        logger.error("Empty query provided")
        return

    # ---- DB ----

    logger.info("Processing query: %s", text)
    get_match_for_text(text)

if __name__ == "__main__":
    main()
