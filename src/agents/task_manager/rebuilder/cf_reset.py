from datetime import datetime, timezone
from src.db import get_collection
from src.agents.task_manager.utils.cf_engine import process_event

events_col = get_collection("events")
cf_col = get_collection("context_fingerprints")
edges_col = get_collection("event_cf_edges")


def reset_cf_state():
    cf_col.delete_many({})
    edges_col.delete_many({})
