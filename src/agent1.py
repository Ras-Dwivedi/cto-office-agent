import time
import traceback

from .email_reader import fetch_new_emails
from .task_extractor import extract_tasks
from .task_store import store_tasks
from .config import EMAIL_POLL_SECONDS
import logging
logger = logging.getLogger(__name__)

def run_agent():
    print("📥 Agent-1 running (incremental email ingestion)...")

    while True:
        emails = fetch_new_emails()

        for email in emails:
            # print("fetching email", email)
            try:
                tasks = extract_tasks(email)
            except Exception as e:
                logger.exception(e)
                logger.error("unable to extract tasks from email")
                continue

            if tasks:
                try:
                    store_tasks(tasks, email["uid"])
                    print(f"📝 {len(tasks)} task(s) created from email UID {email['uid']}")
                except:
                    logger.exception("failed to store tasks")
                    logger.error(str(tasks))
            else:
                print("No tasks found for email UID {email['uid']}")

        time.sleep(EMAIL_POLL_SECONDS)

if __name__ == "__main__":
    run_agent()
