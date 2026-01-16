import math
import re
from collections import defaultdict, Counter
from datetime import datetime

from src.db import get_collection
from src.agents.utils.logger import logger
from src.agents.judgement.event_matcher import _extract_text
from src.agents.judgement.utils import MIN_WORD_LEN, MIN_PROJECT_FREQ, TOP_K, STOPWORDS, tokenize, \
    extract_nouns_and_phrases, is_identifier_noise, infra_penalty, is_geography_token, geo_project_affinity, \
    geo_ambiguity_penalty, is_person_name, is_semantic_noise
from src.config.Project_identifiers import PROJECT_KEYWORDS
# --------------------------------------------------
# Configuration
# --------------------------------------------------




# --------------------------------------------------
# Project Anchor Detection
# --------------------------------------------------

def extract_project_signals(text, PROJECT_REGISTRY):
    text_l = text.lower()
    hits = set()

    for project, meta in PROJECT_REGISTRY.items():
        for alias in meta.get("org_aliases", []):
            if alias.lower() in text_l:
                hits.add(project)
                break
        for kw in meta.get("tech_keywords", []):
            if kw.lower() in text_l:
                hits.add(project)
                break

    return hits
# --------------------------------------------------
# Core Discovery Engine
# --------------------------------------------------

# --------------------------------------------------
# Core Discovery Engine
# --------------------------------------------------

def discover_project_keywords(PROJECT_KEYWORDS):
    """
    Discover high-signal project-specific keywords using:
    - Anchored TF-IDF
    - POS filtering
    - Noise suppression
    - Cross-project ambiguity penalty
    - Geography-aware bias (NEW)
    """

    collections = [
        (get_collection("tasks"), "task"),
        (get_collection("events"), "event"),
        (get_collection("work"), "work"),
        (get_collection("decisions"), "decision"),
    ]

    project_tokens = defaultdict(list)
    project_phrases = defaultdict(list)
    global_df = Counter()

    # -----------------------------
    # Phase 1: Corpus construction
    # -----------------------------
    for col, obj_type in collections:
        logger.info("Scanning %s collection", obj_type)

        for obj in col.find({}):
            text = _extract_text(obj, obj_type)
            if not text:
                continue

            projects = extract_project_signals(text, PROJECT_KEYWORDS)
            if not projects:
                continue

            tokens, phrases = extract_nouns_and_phrases(text)
            unique_tokens = set(tokens + phrases)

            for t in unique_tokens:
                global_df[t] += 1

            for project in projects:
                project_tokens[project].extend(tokens)
                project_phrases[project].extend(phrases)

    total_docs = sum(global_df.values()) + 1

    # -----------------------------
    # Phase 2: TF-IDF + penalties
    # -----------------------------
    results = {}

    for project in PROJECT_KEYWORDS:
        tf = Counter(project_tokens.get(project, []))
        tf_phrases = Counter(project_phrases.get(project, []))

        scores = {}

        # -------- single words --------
        for word, freq in tf.items():
            if freq < MIN_PROJECT_FREQ:
                continue
            if is_semantic_noise(word):
                continue
            # if is_identifier_noise(word):
            #     continue
            # if is_person_name(word):
            #     continue

            df = global_df.get(word, 1)
            idf = math.log(total_docs / df)

            ambiguity = sum(
                1 for p in project_tokens if word in project_tokens[p]
            )

            base_score = (freq * idf) / max(ambiguity, 1)
            base_score *= infra_penalty(word)

            # -------- geography bias (NEW) --------
            if is_geography_token(word, PROJECT_KEYWORDS):
                affinity = geo_project_affinity(word, project, PROJECT_KEYWORDS)
                base_score *= (1.2 if affinity > 0 else 0.5)
                base_score *= geo_ambiguity_penalty(word, PROJECT_KEYWORDS)

            scores[word] = base_score

        # -------- phrases --------
        for phrase, freq in tf_phrases.items():
            if freq < 2:
                continue

            df = global_df.get(phrase, 1)
            idf = math.log(total_docs / df)

            ambiguity = sum(
                1 for p in project_phrases if phrase in project_phrases[p]
            )

            score = (freq * idf * 1.5) / max(ambiguity, 1)

            # geography phrases get same treatment
            for token in phrase.split():
                if is_geography_token(token, PROJECT_KEYWORDS):
                    affinity = geo_project_affinity(token, project, PROJECT_KEYWORDS)
                    score *= (1.2 if affinity > 0 else 0.5)
                    score *= geo_ambiguity_penalty(token, PROJECT_KEYWORDS)

            scores[phrase] = score

        if not scores:
            results[project] = {"suggested_keywords": {}}
            continue

        # normalize
        max_score = max(scores.values())
        scores = {
            k: round(v / max_score, 3)
            for k, v in scores.items()
        }

        results[project] = {
            "suggested_keywords": dict(
                sorted(scores.items(), key=lambda x: x[1], reverse=True)[:TOP_K]
            )
        }

    return results


suggestions = discover_project_keywords(PROJECT_KEYWORDS)

for project, data in suggestions.items():
    print("\nPROJECT:", project)
    for kw, score in data["suggested_keywords"].items():
        print(f"  {kw}: {score}")