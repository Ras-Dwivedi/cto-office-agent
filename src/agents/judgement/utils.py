import re
import spacy

MAX_RESULTS = 10
SCORE_THRESHOLD = 0.25
TIME_DECAY_HOURS = 72

MIN_WORD_LEN = 3
MIN_PROJECT_FREQ = 3
TOP_K = 30

MIN_EMAIL_FREQ = 2
SHORT_EMAIL_TOKEN_PENALTY = 0.6
THREAD_REDUNDANCY_PENALTY = 0.7
# --------------------------------------------------
# NLP Setup
# --------------------------------------------------

nlp = spacy.load("en_core_web_sm")

# --------------------------------------------------
# Stopword Taxonomy (CRITICAL)
# --------------------------------------------------

BASE_STOPWORDS = {
    "the", "is", "and", "to", "of", "in", "on", "for", "with",
    "a", "an", "by", "at", "from", "this", "that"
}

FUNCTION_STOPWORDS = {
    "has", "have", "had", "will", "would", "should", "not",
    "any", "each", "does", "been", "were", "was", "are",
}

COMMUNICATION_STOPWORDS = {
    "email", "fwd", "forwarded", "regarding", "request",
    "meeting", "discussion", "call", "room", "review",
}

SYSTEM_STOPWORDS = {
    "web", "website", "application", "portal", "documents",
    "submission", "attached", "provide", "provided",
}

IDENTITY_STOPWORDS = {
    "ras", "team", "customer", "manager", "senior",
}
ADMIN_DOMAIN_STOPWORDS = {
    "credit", "card", "bank", "invoice", "payment",
    "approval", "experience", "letter", "salary",
    "account", "finance", "hdfc", "sbi",
}

PERSON_NAME_STOPWORDS = {
    "negi", "singh", "kumar", "ajul", "anamika",
    "manindra", "ranjeet", "kuldip", "bajpai"
}

INFRA_KEYWORDS = {
    "vpn", "user", "account", "display", "units",
    "server", "desktop", "laptop", "monitor",
}
HR_STOPWORDS = {
    "notice period", "leave deduction", "offer",
    "experience letter", "joining", "salary",
    "designation", "role"
}

STOPWORDS = (
    BASE_STOPWORDS
    | FUNCTION_STOPWORDS
    | COMMUNICATION_STOPWORDS
    | SYSTEM_STOPWORDS
    | IDENTITY_STOPWORDS
    | ADMIN_DOMAIN_STOPWORDS
)


ACTION_VERBS = {
    "create": ["write", "draft", "design", "prepare", "build"],
    "review": ["review", "verify", "audit", "check"],
    "decide": ["approve", "reject", "finalize", "decide"],
    "communicate": ["call", "email", "meet", "discuss"],
    "analyze": ["analyze", "evaluate", "think", "assess"]
}
# Flatten verb list
ALL_VERBS = {v for vs in ACTION_VERBS.values() for v in vs}



def infra_penalty(word):
    return 0.4 if any(k in word for k in INFRA_KEYWORDS) else 1.0


IDENTIFIER_PATTERN = re.compile(
    r"^[a-z]{1,4}\d{3,}$|^\d{3,}$|^[a-z0-9\+\-]{6,}$"
)


def is_identifier_noise(token: str) -> bool:
    return bool(IDENTIFIER_PATTERN.match(token))

def is_person_name(phrase: str):
    tokens = phrase.lower().split()
    return any(t in PERSON_NAME_STOPWORDS for t in tokens)

def is_person_name_phrase(phrase: str) -> bool:
    tokens = re.split(r"[ _\-]+", phrase.lower())
    return any(tok in PERSON_NAME_STOPWORDS for tok in tokens)

def is_hr_stopword(phrase: str):
    tokens = phrase.lower().split()
    return any(t in HR_STOPWORDS for t in tokens)

def is_semantic_noise(text: str) -> bool:
    """
    Returns True if the given token or phrase should be excluded
    from semantic discovery and scoring.

    This function centralizes:
    - identifier noise
    - person names
    - HR / employment plane terms
    """

    if not text:
        return True

    text_l = text.lower().strip()
    tokens = text_l.split()

    # -----------------------------
    # 1. Identifier / code noise
    # -----------------------------
    # Examples: wr250527, ioas, tlp, amber+strict
    if len(tokens) == 1 and is_identifier_noise(tokens[0]):
        return True

    # -----------------------------
    # 2. Person name suppression
    # -----------------------------
    # Examples: negi, anamika singh, ajul kumar
    if any(t in PERSON_NAME_STOPWORDS for t in tokens):
        return True

    # -----------------------------
    # 3. HR / employment plane
    # -----------------------------
    # Examples: notice period, leave deduction, offer
    if any(t in HR_STOPWORDS for t in tokens):
        return True

    return False


def normalize(text: str):
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    return set(t for t in tokens if t not in STOPWORDS and len(t) > 2)


def extract_verbs(text: str):
    tokens = normalize(text)
    return set(t for t in tokens if t in ALL_VERBS)


def tokenize(text: str):
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]+", text.lower())
    return [
        w for w in words
        if w not in STOPWORDS and len(w) >= MIN_WORD_LEN
    ]

def _extract_text(obj, obj_type):
    """
    Extract canonical, schema-faithful text for scoring.

    IMPORTANT:
    - This function MUST NOT interpret meaning.
    - It MUST reflect how text is stored, not how it is understood.
    """

    if obj_type == "event":
        payload = obj.get("payload", {})
        return (
            payload.get("title")
            or payload.get("subject")
            or payload.get("task_text")
            or payload.get("decision")
            or ""
        )

    if obj_type == "work":  # pomodoro
        return obj.get("title") or ""

    if obj_type == "task":
        return obj.get("title") or ""

    if obj_type == "interrupt":
        return obj.get("title") or ""

    if obj_type == "decision":
        # Concatenate, but DO NOT summarize or rephrase
        decision = obj.get("decision") or ""
        context = obj.get("context") or ""
        return f"{decision}. {context}".strip()

    # Explicit fallback — visible failure mode
    return None


def extract_nouns_and_phrases(text: str):
    """
    Extract:
    - Nouns / Proper nouns
    - Noun-based bi-grams (e.g. 'seed licensing')
    """
    doc = nlp(text.lower())
    tokens = []
    phrases = []

    prev = None

    for token in doc:
        if token.is_stop:
            prev = None
            continue

        if token.text in STOPWORDS:
            prev = None
            continue

        if token.pos_ not in {"NOUN", "PROPN"}:
            prev = None
            continue

        if len(token.text) < MIN_WORD_LEN:
            prev = None
            continue

        tokens.append(token.text)

        # bi-gram phrase
        if prev:
            phrase = f"{prev} {token.text}"
            phrases.append(phrase)

        prev = token.text

    return tokens, phrases

def extract_geography_signals(text: str, PROJECT_KEYWORDS):
    """
    Returns:
      {
        project: {"jaipur", "rajasthan"}
      }
    """
    text_l = text.lower()
    hits = {}

    for project, meta in PROJECT_KEYWORDS.items():
        geo = meta.get("geography", {})
        matches = set()

        for city in geo.get("cities", []):
            if city.lower() in text_l:
                matches.add(city.lower())

        for state in geo.get("states", []):
            if state.lower() in text_l:
                matches.add(state.lower())

        if matches:
            hits[project] = matches

    return hits

def is_geography_token(word: str, PROJECT_KEYWORDS):
    for meta in PROJECT_KEYWORDS.values():
        geo = meta.get("geography", {})
        if word in geo.get("cities", []) or word in geo.get("states", []):
            return True
    return False


def geo_project_affinity(word: str, project: str, PROJECT_KEYWORDS):
    """
    Returns:
      +1.0 if word belongs to project's geography
      -1.0 if word belongs to some other project's geography
       0.0 if not geography
    """
    for p, meta in PROJECT_KEYWORDS.items():
        geo = meta.get("geography", {})
        if word in geo.get("cities", []) or word in geo.get("states", []):
            return 1.0 if p == project else -1.0
    return 0.0


def geo_ambiguity_penalty(word: str, PROJECT_KEYWORDS):
    appearances = 0
    for meta in PROJECT_KEYWORDS.values():
        geo = meta.get("geography", {})
        if word in geo.get("cities", []) or word in geo.get("states", []):
            appearances += 1
    return 1 / max(appearances, 1)

