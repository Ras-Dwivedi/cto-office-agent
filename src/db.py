from pymongo import MongoClient
from .config import (
    MONGO_USER,
    MONGO_PASS,
    MONGO_HOST,
    MONGO_PORT,
    DB_NAME
)

MONGO_URI = (
    f"mongodb://{MONGO_USER}:{MONGO_PASS}"
    f"@{MONGO_HOST}:{MONGO_PORT}/{DB_NAME}"
    f"?authSource=admin"
)

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

tasks_col = db.tasks
state_col = db.email_state
emails_col = db.raw_emails


def get_last_uid():
    doc = state_col.find_one({"_id": "imap_state"})
    return doc["last_uid"] if doc else 0


def update_last_uid(uid):
    state_col.update_one(
        {"_id": "imap_state"},
        {"$set": {"last_uid": uid}},
        upsert=True
    )

tasks_col = db.tasks
state_col = db.email_state
emails_col = db.raw_emails

def get_last_uid():
    doc = state_col.find_one({"_id": "imap_state"})
    return doc["last_uid"] if doc else 0

def update_last_uid(uid):
    state_col.update_one(
        {"_id": "imap_state"},
        {"$set": {"last_uid": uid}},
        upsert=True
    )
