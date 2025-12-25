import time
import logging

from src.agents.task_creator.email_reader import fetch_new_emails
from src.agents.task_creator.task_extractor import extract_tasks
from src.agents.task_creator.task_store import store_task
from src.config import EMAIL_POLL_SECONDS


# ---------- LOGGING SETUP (ENFORCED) ----------
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


setup_logging()
logger = logging.getLogger("agent.task_creator.agent1")


# ---------- SLEEP CONSTANTS ----------
LONG_SLEEP = 2 * 60 * 60        # 2 hours
SHORT_SLEEP = EMAIL_POLL_SECONDS


# ---------- AGENT LOOP ----------
def run_agent():
    logger.info("📥 Agent-1 started (incremental email ingestion)")

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

            try:
                logger.info("Processing email UID=%s", uid)
                tasks = extract_tasks(email)
            except Exception:
                logger.exception(
                    "❌ Unable to extract tasks from email UID=%s",
                    uid
                )
                continue

            if tasks:
                try:
                    store_task(tasks)
                    logger.info(
                        "📝 Stored %d task(s) from email UID=%s",
                        len(tasks),
                        uid
                    )
                except Exception:
                    logger.exception(
                        "❌ Failed to store tasks from email UID=%s",
                        uid
                    )
            else:
                logger.info(
                    "No actionable tasks found for email UID=%s",
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
