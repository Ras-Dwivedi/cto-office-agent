from imapclient import IMAPClient
import pyzmail
from src.config import IMAP_HOST, EMAIL_USER, EMAIL_PASS
from src.db import get_last_uid, update_last_uid, get_collection

BATCH_SIZE = 10  # max emails per run

emails_col = get_collection("raw_emails")


def fetch_new_emails():
    last_uid = get_last_uid()
    mails = []

    with IMAPClient(IMAP_HOST) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.select_folder("INBOX")

        # Fetch UIDs greater than last processed
        all_uids = server.search([u"UID", f"{last_uid + 1}:*"])

        if not all_uids:
            # No new emails at all
            return {
                "emails": [],
                "exhausted": True
            }

        all_uids = sorted(all_uids)

        # Process only a batch
        uids_to_process = all_uids[:BATCH_SIZE]

        fetch_data = server.fetch(uids_to_process, ["RFC822"])

        for uid in uids_to_process:
            raw = fetch_data[uid][b"RFC822"]
            msg = pyzmail.PyzMessage.factory(raw)

            body = ""
            if msg.text_part:
                body = msg.text_part.get_payload().decode(
                    msg.text_part.charset or "utf-8", errors="ignore"
                )

            mail = {
                "uid": uid,
                "subject": msg.get_subject(),
                "from": msg.get_addresses("from"),
                "body": body[:5000]
            }

            emails_col.insert_one(mail)
            mails.append(mail)

        # Update state ONLY to last processed UID
        update_last_uid(uids_to_process[-1])

        exhausted = len(all_uids) <= BATCH_SIZE

    return {
        "emails": mails,
        "exhausted": exhausted
    }
