import pytest
from datetime import datetime, timezone

from src.agents.task_manager.utils.cf_engine import process_event
from src.db import get_collection


@pytest.fixture(autouse=True)
def clean_db():
    """
    Clean collections before each test.
    """
    contexts_col = get_collection("context_fingerprints")
    edges_col = get_collection("event_cf_edges")

    contexts_col.delete_many({})
    edges_col.delete_many({})

    yield

    contexts_col.delete_many({})
    edges_col.delete_many({})


def is_facet_valid(facet):
    is_valid = False
    for key, value in facet.items():
        if value is not {}:
            is_valid = True
            break
    return is_valid
def test_cf_creation_and_facet_accumulation():
    contexts_col = get_collection("context_fingerprints")

    now = datetime.now(timezone.utc)

    # --------------------------------------------------
    # Event 1: weak decision event (forces CF creation)
    # --------------------------------------------------
    e1_text = "Decision approved"

    h1 = process_event(
        event_id="evt-1",
        event_type="decision.detected",
        event_text=e1_text,
        now=now,
        allow_cf_creation=True
    )

    assert len(h1) == 1
    cf_id = h1[0]["cf_id"]

    cf = contexts_col.find_one({"cf_id": cf_id})
    assert cf is not None

    # Facets should exist (decision → action.decision)
    assert "facets" in cf
    assert cf["facets"] != {}

    assert "action" in cf["facets"]
    assert "decision" in cf["facets"]["action"]
    print("printing CF ------->")
    print(cf["facets"]["action"]["decision"])
    print("Test one ended")
    # --------------------------------------------------
    # Event 2: execution-heavy technical event
    # --------------------------------------------------
    e2_text = "Implement SOC alert correlation and deploy SIEM rules"

    h2 = process_event(
        event_id="evt-2",
        event_type="task_candidate.detected",
        event_text=e2_text,
        now=now,
        allow_cf_creation=True
    )

    assert any(h["cf_id"] == cf_id for h in h2)

    cf = contexts_col.find_one({"cf_id": cf_id})
    print(cf)
    assert is_facet_valid(cf["facets"])

    # Execution facet should now be present
    # assert "nature" in cf["facets"]
    # assert "execution" in cf["facets"]["nature"]
    #
    # # Domain facet should now exist
    # assert "domain" in cf["facets"]
    # assert "cybersecurity" in cf["facets"]["domain"]

    # --------------------------------------------------
    # Event 3: managerial coordination
    # --------------------------------------------------
    e3_text = "Follow up meeting with SOC team for review"

    process_event(
        event_id="evt-3",
        event_type="email.received",
        event_text=e3_text,
        now=now,
        allow_cf_creation=True
    )

    cf = contexts_col.find_one({"cf_id": cf_id})
    print(cf)

    e4_text = "Send email for meeting"

    process_event(
        event_id="evt-4",
        event_type="email.received",
        event_text=e4_text,
        now=now,
        allow_cf_creation=True
    )

    print("<------- printing CF 4------->")
    cf = contexts_col.find_one({"cf_id": cf_id})
    print(cf)
    assert is_facet_valid(cf["facets"])
    #
    # # Coordination should accumulate
    # assert "coordination" in cf["facets"]["action"]
    #
    # # --------------------------------------------------
    # # Stats validation
    # # --------------------------------------------------
    # stats = cf["stats"]
    #
    # assert stats["event_count"] == 3
    # assert stats["by_event_type"]["decision__detected"] == 1
    # assert stats["by_event_type"]["task_candidate__detected"] == 1
    # assert stats["by_event_type"]["email__received"] == 1
    #
    # # --------------------------------------------------
    # # Temporal sanity
    # # --------------------------------------------------
    # assert cf["last_activity"] >= cf["created_at"]
