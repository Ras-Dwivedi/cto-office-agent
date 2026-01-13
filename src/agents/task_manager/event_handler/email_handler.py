import time
from datetime import datetime, timezone

from src.agents.task_manager.email_extractor import (
    extract_tasks,
    extract_decisions,
)
from src.agents.task_manager.utils.task_engine import task_engine
from src.agents.task_manager.utils.event_engine import event_engine
from src.agents.task_manager.utils.attachment.signal_extractor import extract_attachment_signals
from src.config.config import EMAIL_POLL_SECONDS
from src.db import get_collection
from src.agents.task_manager.utils.decision_engine import record_decision
from src.agents.utils.logger import logger
from src.config.config import EMAIL_PROCESSOR_VERSION,EXCLUDED_FOLDERS,EXCLUDED_PREFIXES, CUTOFF_DATE




# =========================================================
# DB COLLECTIONS
# =========================================================

state_col = get_collection("processor_state")

PROCESSOR_NAME = "email_event_agent"

LONG_SLEEP = 2 * 60 * 60
SHORT_SLEEP = EMAIL_POLL_SECONDS
BATCH_LIMIT = 20

emails_col = get_collection("raw_emails")
raw_emails_syn_col = get_collection("email_sync_state")
# =========================================================
# CONSTANTS
# =========================================================

def get_all_folder_list():
    """
    Return the list of all folders known to the email sync state.

    Source of truth:
    - email_sync_state collection
    - One document per folder

    Returns:
        List[str]: folder names
    """
    folders = raw_emails_syn_col.distinct("folder")
    folders = [f for f in folders if f]  # defensive cleanup
    folders.sort()
    return folders

def get_folder_state(folder: str):
    return state_col.find_one({
        "processor": PROCESSOR_NAME,
        "version": EMAIL_PROCESSOR_VERSION,
        "source.type": "email",
        "source.folder": folder,
    })


def update_folder_state(
    folder: str,
    *,
    cursor: dict,
    status: str = "idle",
):
    """
    Persist folder-level cursor state for email ingestion.

    Cursor invariants:
    ------------------
    - Cursor is monotonic
    - Cursor is advanced ONLY after successful processing
    - Cursor uniquely identifies position using (received_at, _id)

    Parameters
    ----------
    folder : str
        Email folder name (e.g., INBOX)

    cursor : dict
        {
            "received_at": datetime,
            "_id": ObjectId
        }

    status : str
        Processor status (idle | running | failed)
    """

    assert "received_at" in cursor, "cursor.received_at required"
    assert "uid" in cursor, "cursor.uid required"

    state_col.update_one(
        {
            "processor": PROCESSOR_NAME,
            "version": EMAIL_PROCESSOR_VERSION,
            "source.type": "email",
            "source.folder": folder,
        },
        {
            "$set": {
                "processor": PROCESSOR_NAME,
                "version": EMAIL_PROCESSOR_VERSION,
                "source": {
                    "type": "email",
                    "folder": folder,
                },
                "cursor": {
                    "received_at": cursor["received_at"],
                    "uid": cursor["uid"],
                },
                "status": status,
                "updated_at": utc_now(),
            }
        },
        upsert=True,
    )

def register_email_event(email: dict):
    email_id = email["_id"]
    uid = email.get("uid")
    received_at = email.get("received_at") or utc_now()
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
            "ingestion_version": EMAIL_PROCESSOR_VERSION,
        },
    )

    logger.info(
        "📨 email.received → %s (UID=%s)",
        email_event["event_id"],
        uid,
    )
    return email_event

def register_attachment_event(attachment, email, email_event):
    uid = email.get("uid")
    received_at = email.get("received_at") or utc_now()
    path = attachment.get("path")
    if not path:
        return

    try:
        sig = extract_attachment_signals(path)
    except Exception as e:
        logger.warning(
            "⚠️ Attachment signal failed UID=%s file=%s: %s",
            uid,
            path,
            e,
        )
        return

    if not sig:
        return

    event_engine.register_event(
        event_type="attachment.signals_detected",
        occurred_at=received_at,
        payload={
            "source": "email",
            "source_ref": email_event["event_id"],
            "email": {
                "uid": uid,
                "subject": email.get("subject"),
                "from": email.get("from"),
            },
            "attachment": {
                "filename": sig["filename"],
                "signal_strength": sig["signal_strength"],
            },
            "signals": sig["signals"],
            "extractor_version": EMAIL_PROCESSOR_VERSION,
        },
    )

def create_email_task(t, email, email_event):
    uid = email.get("uid")
    received_at = email.get("received_at") or utc_now()
    task = task_engine.create_task(
        title=t["title"],
        source="email",
        source_event_id=email_event["event_id"],
        occurred_at=received_at,
        signals={
            "institutional": t.get("institutional"),
            "delegatable": t.get("delegatable"),
            "blocks_others": t.get("blocks_others"),
            "external_dependency": t.get("external_dependency"),
            "due_by": t.get("due_by"),
        },
        meta={
            "email_uid": uid,
            "email_subject": email.get("subject"),
            "email_from": email.get("from"),
        },
    )
    logger.info(
        "📝 Task created %s from email UID=%s",
        task["task_id"],
        uid,
    )

def create_email_decision(d, email, email_event):
    uid = email.get("uid")
    received_at = email.get("received_at") or utc_now()
    decision_record = record_decision(
        event_id=email_event["event_id"],
        decision=d["decision"],
        occurred_at=received_at,
        context=d.get("context"),
        source="email",
        meta={
            "email_uid": uid,
            "confidence": d.get("confidence"),
            "reversible": d.get("reversible"),
            "effective_date": d.get("effective_date"),
        }
    )
    logger.info(f"decision record: {decision_record}")

def process_email(email: dict):
    uid = email.get("uid")
    received_at = email.get("received_at") or utc_now()
    try:
        # =================================================
        # 1️⃣ EMAIL RECEIVED EVENT (FACT)
        # =================================================
        email_event = register_email_event(email)

        # =================================================
        # 2️⃣ ATTACHMENT WEAK SIGNAL EXTRACTION (PURE)
        # =================================================
        for attachment in email.get("attachments", []):
            register_attachment_event(attachment, email, email_event)

        # =================================================
        # 3️⃣ TASK CANDIDATE EXTRACTION (PURE LLM)
        # =================================================
        try:
            tasks = extract_tasks(email)
        except Exception as e:
            logger.warning(
                "⚠️ Task extraction failed UID=%s: %s", uid, e
            )
            tasks = []

        for t in tasks:
            create_email_task(t, email, email_event)

        # =================================================
        # 4️⃣ DECISION EXTRACTION (PURE LLM)
        # =================================================
        try:
            decisions = extract_decisions(email)
        except Exception as e:
            logger.exception("Decision extraction failed UID=%s", uid)
            logger.warning(
                "⚠️ Decision extraction failed UID=%s: %s", uid, e
            )
            decisions = []
            exit()

        for d in decisions:
            create_email_decision(d, email, email_event)
        # =================================================
        # 5️⃣ MARK EMAIL AS PROCESSED (SAFE)
        # =================================================
        emails_col.update_one(
            {"_id": email["_id"]},
            {
                "$set": {
                    "processing": {
                        "status": "processed",
                        "processor": PROCESSOR_NAME,
                        "version": EMAIL_PROCESSOR_VERSION,
                        "last_attempt_at": utc_now(),
                        "error": None,
                    }
                }
            },
        )


    except Exception as e:
        logger.exception("❌ Failed processing email UID=%s", uid)

        emails_col.update_one(
            {"_id": email["_id"]},
            {
                "$set": {
                    "processing": {
                        "status": "failed",
                        "processor": PROCESSOR_NAME,
                        "version": EMAIL_PROCESSOR_VERSION,
                        "last_attempt_at": utc_now(),
                        "error": str(e),
                    }
                }
            },
        )


# =========================================================
# HELPERS
# =========================================================

def utc_now():
    return datetime.now(timezone.utc)

# =========================================================
# AGENT LOOP
# =========================================================
folders = get_all_folder_list()

def run_agent():
    logger.info("📥 Email Event Agent started (raw_emails → events)")

    for folder in folders:
        if folder in EXCLUDED_FOLDERS:
            logger.info("🚫 Skipping folder (excluded): %s", folder)
            continue
        if any(folder.startswith(p) for p in EXCLUDED_PREFIXES):
            logger.info("🚫 Skipping folder (prefix excluded): %s", folder)
            continue

        logger.info("📂 Processing folder %s", folder)

        while True:
            state = get_folder_state(folder) or {}
            cursor = state.get("cursor", {})

            last_received_at = cursor.get("received_at")
            last_uid = cursor.get("uid")

            # -------------------------------------------------
            # Base query (cutoff + skip failed)
            # -------------------------------------------------
            query = {
                "folder": folder,
                "received_at": {"$gte": CUTOFF_DATE},
                "$or": [
                    {"processing.status": {"$exists": False}},
                    {"processing.status": {"$nin": ["failed", "dead"]}},
                ],
            }

            # -------------------------------------------------
            # Monotonic cursor condition
            # -------------------------------------------------
            if last_received_at is not None:
                query.setdefault("$and", []).append(
                    {
                        "$or": [
                            {"received_at": {"$gt": last_received_at}},
                            {
                                "received_at": last_received_at,
                                "uid": {"$gt": last_uid},
                            },
                        ]
                    }
                )

            emails = list(
                emails_col.find(query)
                .sort([("received_at", 1), ("uid", 1)])
                .limit(BATCH_LIMIT)
            )

            if not emails:
                logger.info("✔ Folder %s exhausted", folder)
                break

            logger.info(
                "Processing %d email(s) in folder %s",
                len(emails),
                folder,
            )

            for email in emails:
                uid = email["uid"]

                try:
                    process_email(email)

                    update_folder_state(
                        folder,
                        cursor={
                            "received_at": email["received_at"],
                            "uid": uid,
                        },
                        status="idle",
                    )

                except Exception as e:
                    logger.exception(
                        "❌ Failed processing email uid=%s folder=%s",
                        uid,
                        folder,
                    )

                    emails_col.update_one(
                        {"folder": folder, "uid": uid},
                        {
                            "$set": {
                                "processing": {
                                    "status": "failed",
                                    "error": str(e),
                                    "failed_at": utc_now(),
                                }
                            }
                        },
                    )

                    # 🚨 advance cursor EVEN on failure
                    update_folder_state(
                        folder,
                        cursor={
                            "received_at": email["received_at"],
                            "uid": uid,
                        },
                        status="error",
                    )

            time.sleep(SHORT_SLEEP)
# =========================================================
# CLI ENTRY
# =========================================================

def main():
    run_agent()
    # print(get_all_folder_list())
if __name__ == "__main__":
    main()
