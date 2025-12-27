from src.db import get_collection

tasks_col = get_collection("tasks")
emails_col = get_collection("raw_emails")


def open_email(task_id: str):
    """
    Display the full email associated with a task.
    """

    task = tasks_col.find_one({"task_id": task_id})
    if not task:
        print(f"❌ Task not found: {task_id}")
        return

    email_uid = task.get("email_uid")
    if not email_uid:
        print(f"⚠️ No email associated with task {task_id}")
        return

    email = emails_col.find_one({"uid": email_uid})
    if not email:
        print(f"❌ Email UID {email_uid} not found in raw_emails")
        return

    # ---------- Pretty print ----------
    sender = email.get("from")
    if isinstance(sender, list) and sender:
        sender_str = sender[0][0] or sender[0][1]
    else:
        sender_str = str(sender)

    print("\n📧 EMAIL CONTEXT\n")
    print(f"Task ID : {task_id}")
    print(f"From    : {sender_str}")
    print(f"Subject : {email.get('subject')}")
    print(f"UID     : {email_uid}")
    print("\n" + "-" * 60 + "\n")
    print(email.get("body", "").strip())
    print("\n" + "-" * 60 + "\n")
