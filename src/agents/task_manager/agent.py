import logging
import time
from datetime import datetime, timezone

from src.agents.task_manager.email_extractor import extract_tasks, extract_decisions
from src.agents.task_manager.utils.event_engine import event_engine
from src.config.config import EMAIL_POLL_SECONDS
from src.db import get_collection

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger("agent.email_event_agent")

# =========================================================
# CONSTANTS
# =========================================================

PROCESSOR_NAME = "email_event_agent"
PROCESSOR_VERSION = 1

LONG_SLEEP = 2 * 60 * 60
SHORT_SLEEP = EMAIL_POLL_SECONDS
BATCH_LIMIT = 20

# =========================================================
# DB COLLECTIONS
# =========================================================

emails_col = get_collection("raw_emails")

# =========================================================
# HELPERS
# =========================================================

def utc_now():
    return datetime.now(timezone.utc)

# =========================================================
# AGENT LOOP
# =========================================================

def run_agent():
    logger.info("📥 Email Event Agent started (raw_emails → events)")

    while True:
        # -------------------------------------------------
        # Fetch unprocessed raw emails
        # -------------------------------------------------
        emails = list(
            emails_col.find(
                {
                    "$or": [
                        {"processing": {"$exists": False}},
                        {"processing.status": {"$ne": "processed"}},
                    ]
                }
            )
            .sort("received_at", 1)
            .limit(BATCH_LIMIT)
        )

        if not emails:
            logger.info("📭 No pending emails. Sleeping.")
            time.sleep(LONG_SLEEP)
            continue

        logger.info("Processing %d raw email(s)", len(emails))

        for email in emails:
            email_id = email["_id"]
            uid = email.get("uid")
            received_at = email.get("received_at") or utc_now()

            try:
                # =================================================
                # 1️⃣ EMAIL RECEIVED EVENT (FACT)
                # =================================================
                email_event = event_engine.register_event(
                    event_type="email.received",
                    occurred_at=received_at,
                    payload={
                        "email_uid": uid,
                        "folder": email.get("folder"),
                        "subject": email.get("subject"),
                        "from": email.get("from"),
                        "to": email.get("to"),
                        "raw_email_ref": email_id,
                        "ingestion_version": PROCESSOR_VERSION,
                    },
                )

                logger.info(
                    "📨 email.received → %s (UID=%s)",
                    email_event["event_id"],
                    uid,
                )

                # =================================================
                # 2️⃣ TASK CANDIDATE EXTRACTION (PURE)
                # =================================================
                try:
                    tasks = extract_tasks(email)
                except Exception as e:
                    logger.warning(
                        "⚠️ Task extraction failed UID=%s: %s", uid, e
                    )
                    tasks = []

                for t in tasks:
                    event_engine.register_event(
                        event_type="task.candidate_detected",
                        occurred_at=received_at,
                        payload={
                            "title": t["title"],
                            "source": "email",
                            "source_ref": email_event["event_id"],
                            "signals": {
                                "institutional": t.get("institutional"),
                                "delegatable": t.get("delegatable"),
                                "blocks_others": t.get("blocks_others"),
                                "external_dependency": t.get("external_dependency"),
                                "due_by": t.get("due_by"),
                            },
                            "email": {
                                "uid": uid,
                                "subject": email.get("subject"),
                                "from": email.get("from"),
                            },
                            "extractor_version": PROCESSOR_VERSION,
                        },
                    )

                # =================================================
                # 3️⃣ DECISION EXTRACTION (PURE)
                # =================================================
                try:
                    decisions = extract_decisions(email)
                except Exception as e:
                    logger.warning(
                        "⚠️ Decision extraction failed UID=%s: %s", uid, e
                    )
                    decisions = []

                for d in decisions:
                    event_engine.register_event(
                        event_type="decision.detected",
                        occurred_at=received_at,
                        payload={
                            "decision": d["decision"],
                            "context": d.get("context"),
                            "expected_outcome": d.get("expected_outcome"),
                            "review_date": d.get("review_date"),
                            "source": "email",
                            "source_ref": email_event["event_id"],
                            "email": {
                                "uid": uid,
                                "subject": email.get("subject"),
                                "from": email.get("from"),
                            },
                            "extractor_version": PROCESSOR_VERSION,
                        },
                    )

                # =================================================
                # 4️⃣ MARK EMAIL AS PROCESSED (SAFE)
                # =================================================
                emails_col.update_one(
                    {"_id": email_id},
                    {
                        "$set": {
                            "processing": {
                                "status": "processed",
                                "processor": PROCESSOR_NAME,
                                "version": PROCESSOR_VERSION,
                                "last_attempt_at": utc_now(),
                                "error": None,
                            }
                        }
                    },
                )

            except Exception as e:
                logger.exception("❌ Failed processing email UID=%s", uid)

                # -------------------------------------------------
                # FAILURE STATE (FULL OBJECT UPDATE – SAFE)
                # -------------------------------------------------
                emails_col.update_one(
                    {"_id": email_id},
                    {
                        "$set": {
                            "processing": {
                                "status": "failed",
                                "processor": PROCESSOR_NAME,
                                "version": PROCESSOR_VERSION,
                                "last_attempt_at": utc_now(),
                                "error": str(e),
                            }
                        }
                    },
                )

        time.sleep(SHORT_SLEEP)


# =========================================================
# CLI ENTRY
# =========================================================

def main():
    run_agent()


if __name__ == "__main__":
    main()
