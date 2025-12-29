import time
from datetime import datetime, timezone

from src.agents.task_manager.email_reader import fetch_new_emails
from src.agents.utils.logger import logger
from src.config.config import EMAIL_POLL_SECONDS

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
    logger.info("📥 Email Event Agent started (raw email → events)")

    while True:
        try:
            result = fetch_new_emails()
        except Exception as e:
            logger.exception("❌ Failed to fetch emails")
            time.sleep(SHORT_SLEEP)
            continue

        emails = result.get("emails", [])
        exhausted = result.get("exhausted", True)
        logger.info("Fetched %d email(s)", len(emails))
        time.sleep(LONG_SLEEP if exhausted else SHORT_SLEEP)


# =========================================================
# CLI ENTRY
# =========================================================

def main():
    run_agent()


if __name__ == "__main__":
    main()
