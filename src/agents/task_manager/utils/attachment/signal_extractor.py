"""
Weak Signal Extractor (v1)

Input  : normalized_lines -> List[str]
Output : signals dict

This module intentionally extracts *weak, directional signals*
and avoids summaries, facts, or over-precision.
"""

import re
from collections import Counter
from typing import List, Dict
from src.agents.task_manager.utils.attachment.normalizer import normalize_text
# from src.signals.weak_signal_extractor import extract_signals_from_normalized

# =========================================================
# Configuration / Ontologies
# =========================================================

SECTION_KEYWORDS = {
    "architecture",
    "scope",
    "overview",
    "background",
    "objectives",
    "assumptions",
    "risk",
    "risks",
    "methodology",
    "design",
    "implementation",
    "evaluation",
    "analysis",
    "results",
    "limitations",
    "future work",
    "conclusion",
}

# Personal / system verb ontology
VERB_CLASS_MAP = {
    # Evaluation / thinking
    "propose": "evaluation",
    "analyze": "evaluation",
    "review": "evaluation",
    "assess": "evaluation",
    "evaluate": "evaluation",

    # Design / creation
    "design": "design",
    "define": "design",
    "architect": "design",
    "formalize": "design",

    # Execution
    "implement": "execution",
    "deploy": "execution",
    "develop": "execution",
    "test": "execution",

    # Decision
    "decide": "decision",
    "approve": "decision",
    "finalize": "decision",
}

DOMAIN_LEXICON = {
    "OT security": [
        "scada", "plc", "ics", "substation",
        "iec", "industrial control"
    ],
    "AI monitoring": [
        "anomaly", "model", "training",
        "inference", "machine learning"
    ],
    "Blockchain": [
        "blockchain", "ledger", "smart contract",
        "consensus", "zk", "cryptography"
    ],
    "Cybersecurity": [
        "security", "attack", "threat",
        "vulnerability", "soc", "incident"
    ],
}

QUESTION_CUES = [
    "how",
    "what",
    "why",
    "should we",
    "can we",
    "tbd",
    "open issue",
    "to be validated",
    "not decided",
    "future work",
    "limitation",
    "challenge",
]


# =========================================================
# Helpers
# =========================================================

def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


# =========================================================
# Signal Detectors
# =========================================================

def detect_section_types(lines: List[str]) -> List[str]:
    sections = set()

    for line in lines:
        t = _clean(line).lower()
        if not t:
            continue

        # short, header-like lines
        if len(t.split()) <= 6 and t in SECTION_KEYWORDS:
            sections.add(t)

    return sorted(sections)


def detect_dominant_verbs(lines: List[str], top_k: int = 3) -> List[str]:
    verb_hits = Counter()

    for line in lines:
        words = re.findall(r"\b[a-z]+\b", line.lower())
        for w in words:
            if w in VERB_CLASS_MAP:
                verb_hits[w] += 1

    return [v for v, _ in verb_hits.most_common(top_k)]


def detect_domains(lines: List[str]) -> List[str]:
    text = " ".join(lines).lower()
    domains = []

    for domain, terms in DOMAIN_LEXICON.items():
        hits = sum(1 for t in terms if t in text)
        if hits >= 2:  # spread threshold
            domains.append(domain)

    return domains


def infer_intent(dominant_verbs: List[str]) -> str:
    if not dominant_verbs:
        return "unknown"

    intent_votes = Counter()

    for v in dominant_verbs:
        cls = VERB_CLASS_MAP.get(v)
        if cls:
            intent_votes[cls] += 1

    if not intent_votes:
        return "unknown"

    return intent_votes.most_common(1)[0][0]


def detect_questions(lines: List[str], max_q: int = 5) -> List[str]:
    questions = []

    for line in lines:
        l = _clean(line)
        ll = l.lower()

        if not l:
            continue

        # Explicit questions
        if "?" in l:
            questions.append(l)

        # Implicit / unresolved cues
        elif any(cue in ll for cue in QUESTION_CUES):
            questions.append(l)

        if len(questions) >= max_q:
            break

    return questions


# =========================================================
# Public API (THIS is what you call)
# =========================================================

def extract_signals_from_normalized(
    normalized_lines: List[str]
) -> Dict[str, object]:
    """
    Main entry point.

    normalized_lines:
        List[str] obtained from PDF / DOCX / XLSX normalizer

    returns:
        {
          "dominant_verbs": [...],
          "section_types": [...],
          "domains": [...],
          "intent": "...",
          "questions_implied": [...]
        }
    """

    if not normalized_lines:
        return {
            "dominant_verbs": [],
            "section_types": [],
            "domains": [],
            "intent": "unknown",
            "questions_implied": [],
        }

    lines = [_clean(l) for l in normalized_lines if l and l.strip()]

    dominant_verbs = detect_dominant_verbs(lines)
    section_types = detect_section_types(lines)
    domains = detect_domains(lines)
    intent = infer_intent(dominant_verbs)
    questions = detect_questions(lines)

    return {
        "dominant_verbs": dominant_verbs,
        "section_types": section_types,
        "domains": domains,
        "intent": intent,
        "questions_implied": questions,
    }


# =========================================================
# Optional CLI test
# =========================================================
from pathlib import Path
from typing import Dict, Optional




def extract_attachment_signals(
    attachment_path: str
) -> Optional[Dict[str, object]]:
    """
    Extract weak directional signals from an attachment.

    Responsibilities:
    - Normalize document text
    - Run weak signal extractor
    - Return non-committal signal metadata ONLY
    - NEVER infer tasks, decisions, or facts
    """

    path = Path(attachment_path)

    if not path.exists() or not path.is_file():
        return None

    # ---------------- Normalize ----------------
    try:
        normalized_lines = normalize_text(str(path))
    except Exception:
        # Attachment unreadable → no signal
        return None

    if not normalized_lines:
        return None

    # ---------------- Weak signal extraction ----------------
    signals = extract_signals_from_normalized(normalized_lines)

    # ---------------- Signal strength heuristic ----------------
    strength_score = (
        len(signals["dominant_verbs"]) +
        len(signals["section_types"]) +
        len(signals["domains"]) +
        len(signals["questions_implied"])
    )

    if strength_score >= 6:
        signal_strength = "high"
    elif strength_score >= 3:
        signal_strength = "medium"
    else:
        signal_strength = "low"

    return {
        "filename": path.name,
        "signals": signals,
        "signal_strength": signal_strength,
    }


if __name__ == "__main__":
    sample = [
        "SYSTEM ARCHITECTURE",
        "This document proposes an AI based monitoring system.",
        "Risk Analysis",
        "Scalability remains a concern.",
        "TBD: model validation strategy",
    ]

    from pprint import pprint
    pprint(extract_signals_from_normalized(sample))
