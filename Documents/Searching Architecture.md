Strategy: Matching Work Evidence to Tasks
Core Mental Model

Tasks are hypotheses.
Pomodoros / events are observations.
Decisions are conclusions.

Trying to directly match observations to hypotheses without reasoning layers will fail.

1. Core Insight — Why the Intuition Is Correct
Tasks are intentional

They express goals and desired outcomes.

Examples:

“Prepare draft”

“Review proposal”

“Decide architecture”

They are:

Abstract

Goal-oriented

Stable over time

Pomodoros / Events are behavioral evidence

They capture what actually happened, not why.

Examples:

“Read email”

“Edited doc”

“Call with X”

“Thought about Y”

They are:

Noisy

Fragmented

Low-level

Often ambiguous

Decisions are outcomes

They change system state.

Examples:

“Approved vendor”

“Rejected approach”

“Deferred decision”

They are:

Rare

High-signal

Structurally important

Why naive embedding matching fails

Directly matching tasks ↔ events using embeddings alone fails because:

Events ≠ intent

Tasks ≠ behavior

Semantic similarity ignores structure, phase, and causality

👉 You need a semantic bridge layer, not a single matcher.

2. Correct Architecture: Three-Layer Matching System
Overview

The system must separate recall, reasoning, and classification.

Events
  ↓
Candidate Retrieval (Recall)
  ↓
Semantic Alignment (Precision)
  ↓
Evidence Classification
  ↓
Task State Update

3. Layer A — Candidate Retrieval (Recall-First)

Goal: Don’t miss relevant work.

This layer is intentionally dumb but broad.

Techniques
Method	Purpose
Bag-of-Words / TF-IDF	Catch obvious lexical overlap
Action verb overlap	“review”, “draft”, “discuss”
Entity overlap	Project names, people, systems
Time proximity	Events near task activity window
CF neighborhood	Events already linked to same CF

Output:
A candidate set of 50–200 events max

⚠️ No intelligence here. Only recall.

4. Layer B — Semantic Alignment (Precision)

Goal: Determine whether work actually contributed to the task.

Now apply reasoning-heavy methods.

Inputs Compared

Task intent

Event description

Decision summaries (if any)

Context window (± N surrounding events)

Techniques

Sentence embeddings

Cross-encoder / reranker

Contextual continuity scoring

Scoring Dimensions

Intent alignment — Why was this done?

Action alignment — What was done?

Context continuity — Is this part of an ongoing thread?

Output:
High-confidence task ↔ event matches.

5. Layer C — Evidence Classification

Goal: Understand how an event contributes.

Every matched event must be typed.

Evidence Types

🛠 Execution — writing, coding, building

🧠 Cognitive — thinking, reading, analysis

🗣 Coordination — calls, emails, meetings

⚖️ Decision-forming

❌ Incidental / noise

This explains:

Why 50 pomodoros didn’t close a task

Why effort ≠ progress

6. Action Words Are a First-Class Signal

Action verbs must be explicitly modeled, not buried in embeddings.

Example Action Taxonomy
create:        write, draft, design, build
review:        review, audit, verify, check
decide:        approve, reject, finalize
communicate:  call, email, meet
analyze:       analyze, evaluate, think

Usage

Detect dominant task action class

Detect event action class

Compare them

⚠️ Mismatch is a signal, not a failure

Example:

Task: create

Events: 20 × communicate

→ Task may be blocked, mis-scoped, or prematurely coordinated.

7. Decisions Are the Missing Keystone

Decisions should not be treated as regular events.

They act as:

Closure signals

State transitions

Task phase boundaries

Decision-Aware Logic

If a decision exists:

Boost relevance of preceding aligned events

Suppress unrelated parallel events

Mark task phase as:

completed

blocked

deferred

This eliminates:

Zombie tasks

Endless CF growth

Misattributed work

8. Fixing the Current CF Explosion Problem
Current (Broken) Flow
Events → CFs → Tasks


CFs become:

Pseudo-tasks

Evidence logs

Unbounded containers

Correct Flow
Events
  → Candidate Pool
    → Semantic Alignment
      → Evidence Typing
        → Task State Update
          → CF Consolidation


CFs become:

Context containers

Thread groupings

Supporting structure — not the core model

9. Minimal Implementation Blueprint
Step 1 — Candidate Retrieval

BoW / TF-IDF

Action verbs

Entity extraction

Time windows

Step 2 — Semantic Scoring

Task ↔ event embeddings

Context window similarity

Reranking

Step 3 — Evidence Typing

Execution

Cognitive

Coordination

Decision

Noise

Step 4 — Task Progress Model

Progress ≠ time spent

Progress = correct evidence accumulating

10. Final Principle

Tasks are hypotheses.
Pomodoros are observations.
Decisions are conclusions.