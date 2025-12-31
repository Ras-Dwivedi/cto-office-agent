import logging
import email.utils
import time
from datetime import datetime, timezone
from time import sleep

import pyzmail
from imapclient import IMAPClient

from src.config.config import IMAP_HOST, EMAIL_USER, EMAIL_PASS
from src.db import get_collection
from src.agents.task_manager.utils.attachment.artifact_storage import store_attachment

# =========================================================
# Logging
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger("email_fetcher")

# =========================================================
# Configuration
# =========================================================

MAILBOX = "PRIMARY"
BATCH_SIZE = 10

# =========================================================
# Folder Filters
# =========================================================

EXCLUDED_FOLDERS = {
    "Drafts",
    "Spam",
    "Trash",
    "Bin",
    "Junk",
    "Recommendations",
    "health conference",
    "appstores notification",
    "Digilocker",
    "Credit Card"
    "Archive",
    "hr.travel",
}

EXCLUDED_PREFIXES = (
    "Archives.",
    "Archive.",
    "Trash"
    "Trash."
)

# =========================================================
# DB Collections
# =========================================================

emails_col = get_collection("raw_emails")
state_col = get_collection("email_sync_state")

# =========================================================
# State Helpers
# =========================================================

def get_last_uid(mailbox: str, folder: str) -> int:
    doc = state_col.find_one({"mailbox": mailbox, "folder": folder})
    last_uid = doc["last_uid"] if doc else 0
    logger.debug(
        "State lookup mailbox=%s folder=%s last_uid=%s",
        mailbox, folder, last_uid,
    )
    return last_uid


def update_last_uid(mailbox: str, folder: str, uid: int):
    state_col.update_one(
        {"mailbox": mailbox, "folder": folder},
        {
            "$set": {
                "last_uid": uid,
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )
    logger.info(
        "State advanced mailbox=%s folder=%s last_uid=%s",
        mailbox, folder, uid,
    )

# =========================================================
# Folder Discovery
# =========================================================

def list_folders(server):
    folders = []
    for _, _, name in server.list_folders():
        folder = name.decode() if isinstance(name, bytes) else name
        folders.append(folder)

    logger.info("Discovered %d folders", len(folders))
    return folders

# =========================================================
# Email Fetcher
# =========================================================

def fetch_new_emails():
    collected = []
    exhausted = True

    logger.info("📥 Starting email fetch (mailbox=%s)", MAILBOX)

    with IMAPClient(IMAP_HOST) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        logger.info("Connected to IMAP server %s", IMAP_HOST)

        for folder in list_folders(server):
            logger.info("📂 Processing folder: %s", folder)
            server.select_folder(folder)
            if folder in EXCLUDED_FOLDERS:
                logger.info("🚫 Skipping folder (excluded): %s", folder)
                continue
            if any(folder.startswith(p) for p in EXCLUDED_PREFIXES):
                logger.info("🚫 Skipping folder (prefix excluded): %s", folder)
                continue

            last_uid = get_last_uid(MAILBOX, folder)
            logger.info(
                "Resuming folder=%s from UID=%s",
                folder, last_uid,
            )

            uids = server.search(["UID", f"{last_uid + 1}:*"])

            if not uids:
                logger.info("No new emails in folder=%s", folder)
                continue

            uids = sorted(uids)
            batch = uids[:BATCH_SIZE]

            logger.info(
                "Fetching %d email(s) from folder=%s (UID %s → %s)",
                len(batch),
                folder,
                batch[0],
                batch[-1],
            )

            fetch_data = server.fetch(batch, ["RFC822", "INTERNALDATE"])
            max_uid_processed = last_uid

            for uid in batch:
                raw = fetch_data[uid][b"RFC822"]
                internal_date = fetch_data[uid].get(b"INTERNALDATE")

                msg = pyzmail.PyzMessage.factory(raw)

                # -------------------------
                # Email body
                # -------------------------
                body = ""
                if msg.text_part:
                    body = msg.text_part.get_payload().decode(
                        msg.text_part.charset or "utf-8",
                        errors="ignore",
                    )

                # -------------------------
                # Dates
                # -------------------------
                sent_at = None
                try:
                    date_hdr = msg.get_decoded_header("date")
                    if date_hdr:
                        sent_at = email.utils.parsedate_to_datetime(date_hdr)
                        if sent_at.tzinfo is None:
                            sent_at = sent_at.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

                received_at = (
                    internal_date.astimezone(timezone.utc)
                    if internal_date
                    else None
                )

                # -------------------------
                # Attachments (NEW)
                # -------------------------
                attachments = []

                for part in msg.mailparts:
                    if part.is_body:
                        continue

                    if not part.filename:
                        continue

                    payload = part.get_payload()
                    if not payload:
                        continue

                    artifact_id = store_attachment(payload)

                    attachments.append({
                        "artifact_id": artifact_id,
                        "filename": part.filename,
                        "content_type": part.type,
                        "size_kb": len(payload) // 1024,
                    })

                    logger.info(
                        "📎 Attachment stored uid=%s file=%s sha=%s",
                        uid,
                        part.filename,
                        artifact_id[:12],
                    )

                # -------------------------
                # Email document
                # -------------------------
                email_doc = {
                    "mailbox": MAILBOX,
                    "folder": folder,
                    "uid": uid,
                    "subject": msg.get_subject(),
                    "from": msg.get_addresses("from"),
                    "to": msg.get_addresses("to"),
                    "body": body[:5000],
                    "sent_at": sent_at,
                    "received_at": received_at,
                    "attachments": attachments,  # 👈 NEW
                    "ingested_at": datetime.now(timezone.utc),
                }
                emails_col.update_one(
                    {
                        "mailbox": MAILBOX,
                        "folder": folder,
                        "uid": uid,
                    },
                    {"$set": email_doc},
                    upsert=True,
                )

                collected.append(email_doc)
                max_uid_processed = uid



            update_last_uid(MAILBOX, folder, max_uid_processed)

            if len(uids) > BATCH_SIZE:
                exhausted = False
                logger.info(
                    "Folder %s not exhausted (%d remaining)",
                    folder,
                    len(uids) - BATCH_SIZE,
                )
            else:
                logger.info("Folder %s exhausted", folder)

    logger.info(
        "📦 Fetch complete: %d email(s), exhausted=%s",
        len(collected),
        exhausted,
    )

    return {
        "emails": collected,
        "exhausted": exhausted,
    }

# =========================================================
# CLI Entry (optional)
# =========================================================

if __name__ == "__main__":
    result = fetch_new_emails()
    print(
        f"Fetched {len(result['emails'])} emails | Exhausted: {result['exhausted']}"
    )
