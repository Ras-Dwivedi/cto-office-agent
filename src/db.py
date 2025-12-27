from pymongo import MongoClient
from src.config.config import (
    MONGO_USER,
    MONGO_PASS,
    MONGO_HOST,
    MONGO_PORT,
    DB_NAME
)

# ---------------- Mongo Connection ----------------

MONGO_URI = (
    f"mongodb://{MONGO_USER}:{MONGO_PASS}"
    f"@{MONGO_HOST}:{MONGO_PORT}/{DB_NAME}"
    f"?authSource=admin"
)

_client = None
_db = None


def get_db():
    global _client, _db

    if _db is None:
        _client = MongoClient(MONGO_URI)
        _db = _client[DB_NAME]

    return _db


def get_collection(name: str):
    return get_db()[name]

# ---------------- Email State Helpers ----------------
# (kept here because they are infra-state, not logic)

def get_last_uid():
    state_col = get_collection("email_state")
    doc = state_col.find_one({"_id": "imap_state"})
    return doc["last_uid"] if doc else 0


def update_last_uid(uid: int):
    state_col = get_collection("email_state")
    state_col.update_one(
        {"_id": "imap_state"},
        {"$set": {"last_uid": uid}},
        upsert=True
    )
