import time
from .email_reader import fetch_new_emails
from .task_extractor import extract_tasks
from .task_store import store_tasks
from .config import EMAIL_POLL_SECONDS


def run_agent():
    print("📥 Agent-1 running (incremental email ingestion)...")

    while True:
        emails = fetch_new_emails()

        for email in emails:
            # print("fetching email", email)
            tasks = extract_tasks(email)
            if tasks:
                store_tasks(tasks, email["uid"])
                print(f"📝 {len(tasks)} task(s) created from email UID {email['uid']}")
            else:
                print("No tasks found for email UID {email['uid']}")

        time.sleep(EMAIL_POLL_SECONDS)

if __name__ == "__main__":
    run_agent()
