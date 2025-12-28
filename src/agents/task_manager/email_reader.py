from imapclient import IMAPClient
import pyzmail
import email.utils
from datetime import datetime, timezone

from src.config.config import IMAP_HOST, EMAIL_USER, EMAIL_PASS
from src.db import get_collection

# =========================================================
# Configuration
# =========================================================

BATCH_SIZE = 10
IGNORED_FOLDERS = {}

# =========================================================
# DB Collections
# =========================================================

emails_col = get_collection("raw_emails")
state_col = get_collection("email_sync_state")

# =========================================================
# State Helpers
# =========================================================

def get_last_uid(folder: str) -> int:
    doc = state_col.find_one({"folder": folder})
    return doc["last_uid"] if doc else 0


def update_last_uid(folder: str, uid: int):
    state_col.update_one(
        {"folder": folder},
        {"$set": {"last_uid": uid}},
        upsert=True
    )

# =========================================================
# Folder Discovery
# =========================================================

def list_inbox_folders(server):
    folders = []

    for _, _, name in server.list_folders():
        folder = name.decode() if isinstance(name, bytes) else name

        # if not folder.upper().startswith("INBOX"):
        #     continue

        # if folder in IGNORED_FOLDERS:
        #     continue

        folders.append(folder)

    return folders

# =========================================================
# Email Fetcher
# =========================================================

def fetch_new_emails():
    collected_emails = []
    exhausted = True

    with IMAPClient(IMAP_HOST) as server:
        server.login(EMAIL_USER, EMAIL_PASS)

        folders = list_inbox_folders(server)

        for folder in folders:
            server.select_folder(folder)

            last_uid = get_last_uid(folder)
            uids = server.search(["UID", f"{last_uid + 1}:*"])

            if not uids:
                continue

            uids = sorted(uids)
            uids_to_process = uids[:BATCH_SIZE]

            fetch_data = server.fetch(
                uids_to_process,
                ["RFC822", "INTERNALDATE"]
            )

            for uid in uids_to_process:
                raw = fetch_data[uid][b"RFC822"]
                internal_date = fetch_data[uid].get(b"INTERNALDATE")

                msg = pyzmail.PyzMessage.factory(raw)

                # ---------------- Body ----------------
                body = ""
                if msg.text_part:
                    body = msg.text_part.get_payload().decode(
                        msg.text_part.charset or "utf-8",
                        errors="ignore"
                    )

                # ---------------- Sent date (header) ----------------
                sent_at = None
                try:
                    date_hdr = msg.get_decoded_header("date")
                    if date_hdr:
                        sent_at = email.utils.parsedate_to_datetime(date_hdr)
                        if sent_at.tzinfo is None:
                            sent_at = sent_at.replace(tzinfo=timezone.utc)
                except Exception:
                    sent_at = None

                # ---------------- Received date (IMAP) ----------------
                received_at = None
                if internal_date:
                    received_at = internal_date.astimezone(timezone.utc)

                email_doc = {
                    "folder": folder,
                    "uid": uid,
                    "subject": msg.get_subject(),
                    "from": msg.get_addresses("from"),
                    "to": msg.get_addresses("to"),
                    "body": body[:5000],

                    # 🔑 Temporal fields
                    "sent_at": sent_at,
                    "received_at": received_at,
                    "ingested_at": datetime.utcnow().replace(tzinfo=timezone.utc),
                }

                emails_col.insert_one(email_doc)
                collected_emails.append(email_doc)

            update_last_uid(folder, uids_to_process[-1])

            if len(uids) > BATCH_SIZE:
                exhausted = False

    return {
        "emails": collected_emails,
        "exhausted": exhausted
    }

# =========================================================
# CLI Entry
# =========================================================

if __name__ == "__main__":
    result = fetch_new_emails()
    print(f"Fetched {len(result['emails'])} emails | Exhausted: {result['exhausted']}")
