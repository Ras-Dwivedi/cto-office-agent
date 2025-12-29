import time
import logging
from datetime import datetime, timezone

from src.agents.task_manager.email_reader import fetch_new_emails
from src.agents.task_manager.task_extractor import extract_tasks
from src.agents.task_manager.utils.cf_engine import process_event
from src.agents.task_manager.utils.event_engine import event_engine
from src.config.config import EMAIL_POLL_SECONDS


# =========================================================
# LOGGING
# =========================================================

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

setup_logging()
logger = logging.getLogger("agent.email_event_ingestor")


# =========================================================
# CONSTANTS
# =========================================================

LONG_SLEEP = 2 * 60 * 60
SHORT_SLEEP = EMAIL_POLL_SECONDS


# =========================================================
# HELPERS
# =========================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# =========================================================
# AGENT LOOP
# =========================================================

def run_agent():
    logger.info("📥 Email Event Agent started (EventEngine → CF)")

    while True:
        try:
            result = fetch_new_emails()
        except Exception:
            logger.exception("❌ Failed to fetch emails")
            time.sleep(SHORT_SLEEP)
            continue

        emails = result.get("emails", [])
        exhausted = result.get("exhausted", True)

        logger.info("Fetched %d email(s)", len(emails))

        for email in emails:
            uid = email.get("uid")
            received_at = email.get("received_at") or utc_now()

            # -------------------------------------------------
            # 1️⃣ EMAIL RECEIVED EVENT (FACT)
            # -------------------------------------------------
            try:
                email_event = event_engine.register_event(
                    event_type="email.received",
                    occurred_at=received_at,
                    payload={
                        "uid": uid,
                        "subject": email.get("subject"),
                        "from": email.get("from"),
                    },
                )

                process_event(
                    event_id=email_event["event_id"],
                    event_type="email",
                    event_text=email.get("subject", ""),
                    now=received_at,
                )

            except Exception:
                logger.exception("❌ Failed to register email.received UID=%s", uid)
                continue

            # -------------------------------------------------
            # 2️⃣ TASK CANDIDATE EXTRACTION (PURE)
            # -------------------------------------------------
            try:
                extracted_tasks = extract_tasks(email)
            except Exception:
                logger.exception("❌ Task extraction failed for UID=%s", uid)
                continue

            if not extracted_tasks:
                continue

            # -------------------------------------------------
            # 3️⃣ TASK CANDIDATE EVENTS (NOT TASKS)
            # -------------------------------------------------
            for t in extracted_tasks:
                try:
                    candidate_event = event_engine.register_event(
                        event_type="task.candidate_detected",
                        occurred_at=received_at,
                        payload={
                            "title": t["title"],
                            "source": "email",
                            "source_ref": str(uid),
                            "email": {
                                "uid": uid,
                                "subject": email.get("subject"),
                                "from": email.get("from"),
                            },
                            "signals": {
                                "institutional": t.get("institutional"),
                                "delegatable": t.get("delegatable"),
                                "blocks_others": t.get("blocks_others"),
                                "external_dependency": t.get("external_dependency"),
                                "due_by": t.get("due_by"),
                            },
                        },
                    )

                    process_event(
                        event_id=candidate_event["event_id"],
                        event_type="task_candidate",
                        event_text=t["title"],
                        now=received_at,
                    )

                    logger.info(
                        "🧠 Task candidate emitted (email UID=%s → %s)",
                        uid,
                        candidate_event["event_id"],
                    )

                except Exception:
                    logger.exception(
                        "❌ Failed to emit task candidate (email UID=%s)", uid
                    )

        time.sleep(LONG_SLEEP if exhausted else SHORT_SLEEP)


# =========================================================
# CLI ENTRY
# =========================================================

def main():
    run_agent()


if __name__ == "__main__":
    main()
