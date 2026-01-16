from src.agents.judgement.project_keyword_discovery import extract_project_signals, discover_project_keywords
from src.agents.judgement.utils import extract_nouns_and_phrases, THREAD_REDUNDANCY_PENALTY, MIN_EMAIL_FREQ, \
    is_semantic_noise, infra_penalty, SHORT_EMAIL_TOKEN_PENALTY, is_geography_token, geo_project_affinity, \
    geo_ambiguity_penalty, TOP_K, is_person_name_phrase, is_person_name
from src.agents.utils.logger import logger
from src.config.Project_identifiers import PROJECT_KEYWORDS
from src.db import get_collection
import re
from typing import Dict
from collections import defaultdict, Counter
import math

email_col = get_collection(("raw_emails"))


REPLY_SEPARATORS = [
    r"^-----Original Message-----",
    r"^On .* wrote:",
    r"^From: .*",
    r"^Sent: .*",
    r"^Subject: .*",
]
SIGNATURE_MARKERS = [
    r"^--\s*$",
    r"^thanks[, ]*$",
    r"^thanks and regards",
    r"^regards[, ]*$",
    r"^best regards",
    r"^sincerely",
]


DISCLAIMER_PATTERNS = [
    r"this email.*confidential",
    r"intended solely for",
    r"unauthorized use.*prohibited",
    r"views expressed.*sender",
]



def extract_email_text(email: Dict) -> str:
    subject = email.get("subject", "") or ""
    body = email.get("body", "") or ""
    return f"{subject}\n\n{body}"



def strip_reply_chains(text: str) -> str:
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        if any(re.match(pat, line.strip(), re.IGNORECASE) for pat in REPLY_SEPARATORS):
            break
        cleaned.append(line)

    return "\n".join(cleaned)


def strip_signature(text: str) -> str:
    lines = text.splitlines()
    result = []

    for i, line in enumerate(lines):
        if any(re.match(pat, line.strip(), re.IGNORECASE) for pat in SIGNATURE_MARKERS):
            break
        result.append(line)

    return "\n".join(result)


def strip_legal_disclaimer(text: str) -> str:
    lowered = text.lower()

    for pat in DISCLAIMER_PATTERNS:
        match = re.search(pat, lowered, re.DOTALL)
        if match:
            return text[:match.start()]

    return text

def normalize_text(text: str) -> str:
    text = text.lower()                     # normalize casing
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{2,}", "\n\n", text)   # collapse blank lines
    text = re.sub(r"[ \t]+", " ", text)     # collapse spaces
    return text.strip()


def preprocess_email(email: Dict) -> str:
    text = extract_email_text(email)
    text = strip_reply_chains(text)
    text = strip_signature(text)
    text = strip_legal_disclaimer(text)
    text = normalize_text(text)
    return text

def _extract_email_text(email):
    if not email:
        return None

    cleaned = preprocess_email(email)
    if len(cleaned.split()) < 6:   # suppress "ok / done / works now"
        return None

    return cleaned

def _email_thread_key(email):
    subject = (email.get("subject") or "").lower()
    subject = re.sub(r"^(re:|fw:|fwd:)\s*", "", subject)
    return subject.strip()


def discover_project_keywords_from_emails(PROJECT_KEYWORDS):
    """
    Discover high-signal project-specific keywords from raw emails using:
    - Preprocessed email text
    - Anchored TF-IDF
    - Thread redundancy suppression
    - Cross-project ambiguity penalty
    - Geography-aware bias
    """

    email_col = get_collection("emails")

    project_tokens = defaultdict(list)
    project_phrases = defaultdict(list)
    global_df = Counter()
    seen_threads = defaultdict(set)  # project → thread keys

    # -----------------------------
    # Phase 1: Corpus construction
    # -----------------------------
    for email in email_col.find({}):
        text = _extract_email_text(email)
        if not text:
            continue

        projects = extract_project_signals(text, PROJECT_KEYWORDS)
        if not projects:
            continue

        tokens, phrases = extract_nouns_and_phrases(text)
        unique_tokens = set(tokens + phrases)

        for t in unique_tokens:
            global_df[t] += 1

        thread_key = _email_thread_key(email)

        for project in projects:
            # suppress repeated signals from same thread
            if thread_key in seen_threads[project]:
                penalty = THREAD_REDUNDANCY_PENALTY
            else:
                penalty = 1.0
                seen_threads[project].add(thread_key)

            project_tokens[project].extend(tokens * int(penalty * 10))
            project_phrases[project].extend(phrases * int(penalty * 10))

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
            if freq < MIN_EMAIL_FREQ:
                continue
            if is_semantic_noise(word):
                continue

            if is_person_name(word):
                continue
            if is_person_name_phrase(word):
                continue

            df = global_df.get(word, 1)
            idf = math.log(total_docs / df)

            ambiguity = sum(
                1 for p in project_tokens if word in project_tokens[p]
            )

            base_score = (freq * idf) / max(ambiguity, 1)
            base_score *= infra_penalty(word)

            # short-email damping
            if freq <= 2:
                base_score *= SHORT_EMAIL_TOKEN_PENALTY

            # geography bias
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

            score = (freq * idf * 1.3) / max(ambiguity, 1)

            for token in phrase.split():
                if is_geography_token(token, PROJECT_KEYWORDS):
                    affinity = geo_project_affinity(token, project, PROJECT_KEYWORDS)
                    score *= (1.2 if affinity > 0 else 0.5)
                    score *= geo_ambiguity_penalty(token, PROJECT_KEYWORDS)

            scores[phrase] = score

        if not scores:
            results[project] = {"suggested_keywords": {}}
            continue

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

def merge_project_keywords(base, email, email_weight=0.7):
    merged = {}

    for project in base:
        merged[project] = {}

        for k, v in base[project]["suggested_keywords"].items():
            merged[project][k] = v

        for k, v in email.get(project, {}).get("suggested_keywords", {}).items():
            merged[project][k] = max(
                merged[project].get(k, 0),
                round(v * email_weight, 3)
            )

    return merged


# def preprocessor_test():
#     print(preprocess_email({
#       "_id": {
#         "$oid": "6952e560abd6e79fc6efe757"
#       },
#       "mailbox": "PRIMARY",
#       "folder": "VAPT",
#       "uid": 189,
#       "attachments": [],
#       "body": "Dear Gaurav,\r\n\r\nPlease recheck now.\r\nIt will work now.\r\n\r\n\r\n-- \r\nThanks and Regards,\r\nPrajwal Bajpai\r\nComputer Engineer\r\nIIT, Kanpur\r\nEmail: prajwalb@iitk.ac.in\r\nMbl: 09793005891\r\n\r\n\r\n\r\n-----Original Message-----\r\nFrom: gaurav <gaurav@c3ihub.iitk.ac.in> \r\nSent: 20 June 2025 11:25\r\nTo: Prajwal Bajpai <prajwalb@iitk.ac.in>\r\nCc: enquiry <enquiry@c3ihub.iitk.ac.in>; ddia@iitk.ac.in; gvaibhav <gvaibhav@iitk.ac.in>; Ras Dwivedi <ras@c3ihub.iitk.ac.in>; sgaurav@iitk.ac.in; Radharaman <radharaman@c3ihub.iitk.ac.in>; ameyap <ameyap@c3ihub.iitk.ac.in>; Deep Solanki <deep@c3ihub.iitk.ac.in>\r\nSubject: Re: Next round VAPT of new website\r\n\r\nDear Prajwal,\r\n\r\nThe following error is encountered while trying to access User roles - Unable to send email. contact the site administrator. Kindly check this. \r\nI have attached the POC.\r\nThanks and Regards,\r\nGaurav Srivastav\r\n\r\n\r\nOn 2025-06-19 13:37, Prajwal Bajpai wrote:\r\n> Dear Gaurav,\r\n> \r\n> You may access the tickets via logging in to the JIRA Portal mentioned\r\n> links:\r\n> \r\n>  \t* IP1-239 - VAPT Release 2.1 docs: Process Flowchart [1]\r\n> \t* IP1-240 - VAPT Release 2.1 docs: Data Workflow [2]\r\n> \t* IP1-241 - VAPT Release 2.1 docs: Code-level documentation [3]\r\n> \t* IP1-242 - VAPT Release 2.1 docs: API Documentation [4]\r\n> \t* IP1-243 - VAPT Release 2.1 docs: Endpoint Mapping [5]\r\n> \t* IP1-244 - VAPT Release 2.1 docs: Clarifications on Development\r\n> Ownership [6]\r\n> \t* IP1-245 - VAPT Release 2.1 docs: Proper and comprehensive SRS\r\n> Documentation [7]\r\n> \t* IP1-246 - VAPT Release 2.1 docs: Database Documentation [8]\r\n> \r\n> User credentials: webmaster@iitk.ac.in/DDIA_web@6347#\r\n> \r\n> We are sharing it with you and your team for quick reference and\r\n> necessary action.\r\n> \r\n> In case of any suggestions/feedback, please let us know.\r\n> \r\n> --\r\n> \r\n> Thanks and Regards,\r\n> \r\n> Prajwal Bajpai\r\n> \r\n> Computer Engineer\r\n> \r\n> IIT, Kanpur\r\n> \r\n> Email: prajwalb@iitk.ac.in\r\n> \r\n> Mbl: 09793005891\r\n> \r\n> From: Gaurav Srivastav <gaurav@c3ihub.iitk.ac.in>\r\n> Sent: 18 June 2025 18:26\r\n> To: Prajwal Bajpai <prajwalb@iitk.ac.in>; Deep Solanki\r\n> <deep@c3ihub.iitk.ac.in>\r\n> Cc: enquiry <enquiry@c3ihub.iitk.ac.in>; ddia@iitk.ac.in; gvaibhav\r\n> <gvaibhav@iitk.ac.in>; Ras Dwivedi <ras@c3ihub.iitk.ac.in>;\r\n> anand@c3ihub.iitk.ac.in; ameyap <ameyap@c3ihub.iitk.ac.in>; Radharaman\r\n> <radharaman@c3ihub.iitk.ac.in>; sgaurav@iitk.ac.in\r\n> Subject: Re: Next round VAPT of new website\r\n> \r\n> Greetings,\r\n> \r\n> Please provide the access.\r\n> \r\n> 1. radharaman@c3ihub.iitk.ac.in\r\n> \r\n> 2. ameyap@c3ihub.iitk.ac.in\r\n> \r\n> 3. deep@c3ihub.iitk.ac.in\r\n> \r\n> 4. gaurav@c3ihub.iitk.ac.in\r\n> \r\n> Kindly update the credentials as per request from the previous email.\r\n> \r\n> Thanks and Regards,\r\n> \r\n> Gaurav Srivastav\r\n> \r\n> On 6/18/25 5:18 PM, Prajwal Bajpai wrote:\r\n> \r\n>> Dear Deep,\r\n>> \r\n>> This is to inform you that the SUNDEW team has completed all the\r\n>> required documentation asked, and the requested documents have been\r\n>> drafted and uploaded under the respective JIRA tickets referenced\r\n>> below:\r\n>> \r\n>> * IP1-239 - VAPT Release 2.1 docs: Process Flowchart [1]\r\n>> * IP1-240 - VAPT Release 2.1 docs: Data Workflow [2]\r\n>> * IP1-241 - VAPT Release 2.1 docs: Code-level documentation [3]\r\n>> * IP1-242 - VAPT Release 2.1 docs: API Documentation [4]\r\n>> * IP1-243 - VAPT Release 2.1 docs: Endpoint Mapping [5]\r\n>> * IP1-244 - VAPT Release 2.1 docs: Clarifications on Development\r\n>> Ownership [6]\r\n>> * IP1-245 - VAPT Release 2.1 docs: Proper and comprehensive SRS\r\n>> Documentation [7]\r\n>> * IP1-246 - VAPT Release 2.1 docs: Database Documentation [8]\r\n>> \r\n>> We are sharing it with you and your team for quick reference and\r\n>> necessary action.\r\n>> \r\n>> In case of any suggestions/feedback, please let us know.\r\n>> \r\n>> --\r\n>> \r\n>> Thanks and Regards,\r\n>> \r\n>> Prajwal Bajpai\r\n>> \r\n>> Computer Engineer\r\n>> \r\n>> IIT, Kanpur\r\n>> \r\n>> Email: prajwalb@iitk.ac.in\r\n>> \r\n>> Mbl: 09793005891\r\n>> \r\n>> -----Original Message-----\r\n>> From: Prajwal Bajpai <prajwalb@iitk.ac.in>\r\n>> Sent: 06 June 2025 12:28\r\n>> To: Deep Solanki <deep@c3ihub.iitk.ac.in>\r\n>> Cc: enquiry <enquiry@c3ihub.iitk.ac.in>; ddia@iitk.ac.in; Prajwal\r\n>> Bajpai <prajwalb@iitk.ac.in>; gvaibhav <gvaibhav@iitk.ac.in>; Ras\r\n>> Dwivedi <ras@c3ihub.iitk.ac.in>; anand@c3ihub.iitk.ac.in; ameyap\r\n>> <ameyap@c3ihub.iitk.ac.in>; Radharaman\r\n>> <radharaman@c3ihub.iitk.ac.in>; sgaurav@iitk.ac.in; gaurav\r\n>> <gaurav@c3ihub.iitk.ac.in>\r\n>> Subject: RE: Next round VAPT of new website\r\n>> Importance: High\r\n>> \r\n>> Dear Deep,\r\n>> \r\n>> Thanks for your email.\r\n>> \r\n>> The SUNDEW Team has shared an \"API-Documentation\" which is enclosed\r\n>> herewith for your quick reference.\r\n>> \r\n>> The mentioned points will be shared with the concerned SUNDEW team,\r\n>> and we will update you once they provide their feedback.\r\n>> \r\n>> --\r\n>> \r\n>> Thanks and Regards,\r\n>> \r\n>> Prajwal Bajpai\r\n>> \r\n>> Computer Engineer\r\n>> \r\n>> IIT, Kanpur\r\n>> \r\n>> Email: prajwalb@iitk.ac.in\r\n>> \r\n>> Mbl: 09793005891\r\n>> \r\n>> ---",
#       "from": [
#         [
#           "Prajwal Bajpai",
#           "prajwalb@iitk.ac.in"
#         ]
#       ],
#       "ingested_at": {
#         "$date": "2025-12-29T20:32:32.674Z"
#       },
#       "received_at": {
#         "$date": "2025-06-20T06:48:17.000Z"
#       },
#       "sent_at": {
#         "$date": "2025-06-20T06:48:03.000Z"
#       },
#       "subject": "RE: Next round VAPT of new website",
#       "to": [
#         [
#           "gaurav",
#           "gaurav@c3ihub.iitk.ac.in"
#         ]
#       ],
#       "processing": {
#         "status": "processed",
#         "processor": "email_event_agent",
#         "version": 3,
#         "last_attempt_at": {
#           "$date": "2026-01-10T16:11:56.494Z"
#         },
#         "error": None
#
#       }
#     }))

def main():
    logger.info("🚀 Starting project keyword discovery")

    # ---- discover from structured objects ----
    logger.info("🔍 Discovering keywords from tasks / events / work / decisions")
    project_kw = discover_project_keywords(PROJECT_KEYWORDS)

    # ---- discover from raw emails ----
    logger.info("📧 Discovering keywords from raw emails")
    email_kw = discover_project_keywords_from_emails(PROJECT_KEYWORDS)

    # ---- merge results (emails seed, projects stabilize) ----
    logger.info("🔗 Merging project and email keywords")
    merged_kw = merge_project_keywords(project_kw, email_kw)

    # ---- display results ----
    for project, data in merged_kw.items():
        print("\n" + "=" * 60)
        print(f"PROJECT: {project}")
        print("=" * 60)

        keywords = data if isinstance(data, dict) else data.get("suggested_keywords", {})

        if not keywords:
            print("  (no keywords discovered)")
            continue

        for kw, score in keywords.items():
            print(f"  {kw:<35} {score:.3f}")

    logger.info("✅ Project keyword discovery completed")



if __name__ == '__main__':
    # preprocessor_test()
    main()