2️⃣ Correct Architecture: 3-Layer Matching (Very Important)
Layer A — Candidate Retrieval (Recall-first)

Goal: Don’t miss relevant work

Use cheap, broad, recall-heavy methods:

Method	Purpose
Bag-of-words / TF-IDF	Catch obvious overlaps
Action verb overlap	“review”, “draft”, “discuss”
Entity overlap	project names, people, systems
Time proximity	work done near task activity window
CF neighborhood	events already linked to same CF

👉 Output: Candidate Events (50–200 max)
No intelligence yet. Just recall.

Layer B — Semantic Alignment (Precision)

Goal: Is this work actually contributing to the task?

Now apply embedding + context reasoning:

Compare:

Task intent

Event description

Decision summaries (if any)

Use:

Sentence embeddings

Cross-encoder or reranker

Context window (±N events)

Score dimensions:

Intent alignment (why)
Action alignment (what)
Context continuity (ongoing thread?)


👉 Output: High-confidence matches

Layer C — Evidence Classification

Goal: What kind of contribution was this?

Classify matched events as:

🛠 Execution (writing, coding, building)

🧠 Cognitive work (thinking, reading, analysis)

🗣 Coordination (calls, emails)

⚖️ Decision-forming

❌ Incidental / noise

This solves your “why did 50 pomodoros not close a task?” problem.

3️⃣ Action Words Are a First-Class Signal (You were spot on)

You should explicitly model action verbs, not bury them in embeddings.

Example action taxonomy
ACTION_CLASSES = {
  "create": ["write", "draft", "design", "build"],
  "review": ["review", "audit", "verify", "check"],
  "decide": ["approve", "reject", "finalize"],
  "communicate": ["call", "email", "meet"],
  "analyze": ["analyze", "evaluate", "think"]
}


Then compute:

Task → dominant action class

Event → detected action class

⚠️ Mismatch is a red flag, not a failure
(e.g., 20 “communicate” events for a “create” task)