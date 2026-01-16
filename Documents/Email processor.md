
#Preprocessor Pipeline
raw_email_json
   ↓
extract_text()
   ↓
strip_reply_chains()
   ↓
strip_signature()
   ↓
strip_legal_disclaimer()
   ↓
normalize_text()
   ↓
clean_email_text



1️⃣ Why extract Project Keywords from Raw Emails (separately)?

Raw emails contain:

Earliest intent signals (before tasks exist)

Unstructured language (subjects, CCs, forwarded text, signatures)

Project drift signals (scope creep, new actors, new tools)

If you wait for:

Tasks → too late

Events → already structured

👉 Raw emails = project semantic ground truth

2️⃣ Conceptual Model (Recommended)

Introduce a Project Keyword Layer:

Raw Emails
   ↓
Email Keyword Extraction
   ↓
Project Keyword Store (PKS)
   ↓
Used by:
  - Task matching
  - Event linking
  - CF creation
  - Interrupt detection


Think of this as a semantic memory per project.

3️⃣ What Are “Project Keywords” (Precisely)?

Not just keywords. Use 4 classes of signals:

A. Core Domain Terms

Examples:

“VAPT”, “SOC”, “penetration testing”

“blockchain”, “smart contract”

“OT security”, “SCADA”

These define what the project is about.

B. Operational Entities

Examples:

Tools: “Burp”, “Nessus”, “Splunk”

Systems: “SAP”, “SCADA”, “Active Directory”

Standards: “ISO 27001”, “CERT-In”

These help align tasks ↔ emails ↔ events.

C. Stakeholders & Roles

Examples:

“IPA”, “CM office”, “CISO”

“vendor”, “auditor”, “client team”

These help detect coordination-heavy tasks.

D. Action & Risk Vocabulary

Examples:

“closure”, “risk acceptance”, “exception”

“delay”, “urgent”, “blocker”

These are CF multipliers, not just keywords.

4️⃣ Extraction Pipeline (Step-by-Step)
Step 1: Email Preprocessing (Critical)

From each raw email, extract:

email_text = (
    subject +
    cleaned_body +
    thread_context(last_n_replies)
)


Strongly recommended preprocessing:

Remove signatures

Remove legal disclaimers

Collapse quoted replies

Normalize casing

Preserve noun phrases

Step 2: Keyword Candidates Generation (Hybrid)

Use three parallel extractors:

(a) Statistical (Fast & Cheap)

TF-IDF over project-specific emails

Compare against global email corpus

Purpose: find project-specific language

(b) Linguistic (Precise)

Noun phrases

Proper nouns

Acronyms

Examples:

“Safe-to-Host certificate”

“Residual Risk Acceptance”

(c) Semantic (Smart)

Sentence embeddings

Keyphrase extraction (e.g., KeyBERT-style)

Purpose: capture implicit meaning

“Delay due to vendor dependency” → vendor dependency

Step 3: Keyword Scoring & Filtering

Each candidate keyword gets a score:

score =
  tfidf_weight
+ semantic_relevance_to_project
+ recurrence_across_threads
+ role/entity_bonus


Reject keywords that are:

Generic email words (“please”, “attached”)

One-off noise

Social-only (“thanks”, “regards”)

5️⃣ Project Keyword Store (PKS) – Data Model

Minimal but powerful:

{
  "project_id": "ipa_soc",
  "keyword": "risk acceptance",
  "category": "risk_process",
  "confidence": 0.87,
  "first_seen": "2025-12-01",
  "last_seen": "2026-01-12",
  "email_count": 14,
  "boosters": ["urgent", "delay"]
}


This lets keywords evolve over time, not stay static.

6️⃣ How This Improves Task & Event Matching
A. Email → Task Detection

When a new email arrives:

Extract keywords

Match against Project Keyword Store

If match score > threshold → auto-attach project

👉 No more orphan emails.

B. Event → CF Alignment

CF creation becomes keyword-guided:

Email keywords ∩ Project keywords → CF relevance ↑


This fixes your earlier concern:

“I ended up with 1200+ CFs and no tasks”

Because now:

CFs are project-aware

Not just syntactic clusters

C. Interrupt Detection (Bonus)

If an email contains:

High-confidence project keywords

But outside working window / context

→ mark as high-cost interruption

7️⃣ Architecture Fit with Your System

Given your setup:

Raw Email Agent
   ↓
Event Agent
   ↓
CF Engine
   ↓
Task Engine


Add one new micro-layer:

Raw Email Agent
   ↓
📌 Project Keyword Extractor
   ↓
Event Agent
   ↓
CF Engine


This avoids refactoring downstream logic.

8️⃣ Practical Timeline (2–3 Engineers)
Week	Deliverable
1	Email cleaning + noun phrase extraction
2	TF-IDF + semantic extraction
3	Project Keyword Store + scoring
4	Task & event matching integration
5	Threshold tuning + evaluation

You’ll see value by week 2.

9️⃣ Important Design Principle (Please Don’t Skip)

Do NOT hard-assign keywords to projects early.

Let them:

Start as floating

Gain confidence via recurrence

Decay if unused

This avoids semantic lock-in, which kills long-running projects.