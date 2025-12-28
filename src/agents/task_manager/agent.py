import time
import logging
from datetime import datetime, timezone

from src.agents.task_manager.email_reader import fetch_new_emails
from src.agents.task_manager.task_extractor import extract_tasks
from src.agents.task_manager.task_store import store_task
from src.agents.task_manager.utils.cf_engine import process_event
from src.config.config import EMAIL_POLL_SECONDS


# ---------- LOGGING SETUP ----------
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


setup_logging()
logger = logging.getLogger("agent.task_manager.email_ingestor")


# ---------- SLEEP CONSTANTS ----------
LONG_SLEEP = 2 * 60 * 60        # 2 hours
SHORT_SLEEP = EMAIL_POLL_SECONDS


# ---------- AGENT LOOP ----------
def run_agent():
    logger.info("📥 Email Task Agent started (CF-aware)")

    while True:
        try:
            logger.debug("Fetching new emails")
            result = fetch_new_emails()
        except Exception:
            logger.exception("❌ Failed to fetch emails")
            time.sleep(SHORT_SLEEP)
            continue

        emails = result.get("emails", [])
        exhausted = result.get("exhausted", True)

        logger.info(
            "Fetched %d email(s) | exhausted=%s",
            len(emails),
            exhausted
        )

        for email in emails:
            uid = email.get("uid")

            # 🔑 Email receipt time (SOURCE OF TRUTH)
            email_received_at = email.get("received_at")

            # Fallback (should rarely happen)
            if not email_received_at:
                email_received_at = datetime.utcnow().replace(tzinfo=timezone.utc)

            try:
                logger.info("Processing email UID=%s", uid)
                tasks = extract_tasks(email)
            except Exception:
                logger.exception(
                    "❌ Unable to extract tasks from email UID=%s",
                    uid
                )
                continue

            if not tasks:
                logger.info(
                    "No actionable tasks found for email UID=%s",
                    uid
                )
                continue

            for task in tasks:
                try:
                    # ----------------------------------------
                    # 🔑 Set task origin time = email received time
                    # ----------------------------------------
                    task["created_at"] = email_received_at.isoformat()
                    task["last_activity_at"] = email_received_at.isoformat()

                    # ----------------------------------------
                    # Store task (identity owned by task_store)
                    # ----------------------------------------
                    store_task(task)
                    task_id = task.get("task_id")

                    logger.info(
                        "📝 Stored task '%s' (task_id=%s) from email UID=%s",
                        task.get("title"),
                        task_id,
                        uid
                    )

                    # ----------------------------------------
                    # Emit TASK event to CF engine
                    # Use email time, not now()
                    # ----------------------------------------
                    if task_id:
                        process_event(
                            event_id=task_id,
                            event_type="task",
                            event_text=task.get("title", ""),
                            now=email_received_at
                        )
                    else:
                        logger.warning(
                            "⚠️ Skipping CF event for task without task_id (email UID=%s)",
                            uid
                        )

                except Exception:
                    logger.exception(
                        "❌ Failed to process task from email UID=%s",
                        uid
                    )

        if exhausted:
            logger.info("📭 Inbox fully processed. Sleeping for 2 hours.")
            time.sleep(LONG_SLEEP)
        else:
            logger.info("📨 Pending backlog detected. Sleeping briefly.")
            time.sleep(SHORT_SLEEP)


def main():
    run_agent()


if __name__ == "__main__":
    main()
