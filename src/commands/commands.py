from src.agents.task_manager.record_decisions import main as record_decision
from src.agents.task_manager.generate_markdown import main as generate_markdown
from src.agents.task_manager.pomodoro import main as pomodoro
from src.agents.task_manager.agent import main as email_task_creator
from src.agents.task_manager.priority_view import get_priority_task
from src.agents.judgement.morning_brief import morning_judgement_brief
from src.cli.open_email import open_email

# 🔹 NEW: manual event ingestion
from src.agents.task_manager.utils.manual_event_ingestion import main as manual_event_ingest


COMMAND_ROUTES = {
    #========= WORK LOGS ======
    "record-decision": {
        "handler": record_decision,
        "help": "Record a new decision (use --long for detailed entry)"
    },
    "generate-markdown": {
        "handler": generate_markdown,
        "help": "Generate Markdown report from all decisions"
    },
    "pomodoro": {
        "handler": pomodoro,
        "help": "Start a 25-minute Pomodoro session for a task"
    },

    # ---------------- Task creation ----------------
    "create-tasks": {
        "handler": email_task_creator,
        "help": "Read emails and create tasks automatically"
    },

    # ---------------- Priority view ----------------
    "priority": {
        "handler": get_priority_task,
        "help": "Show top 5 highest priority tasks"
    },

    # ------ Morning brief ----------------
    "morning": {
        "handler": morning_judgement_brief,
        "help": "Show morning judgment brief (delegate vs personal focus)"
    },

    "open": {
        "handler": lambda task_id=None: open_email(task_id),
        "help": "Open the full email associated with a task_id"
    },

    #========= MANUAL EVENT INGESTION ======
    "call": {
        "handler": lambda: manual_event_ingest(source="call"),
        "help": "Log a phone call as a work event (one-line summary)"
    },
    "wa": {
        "handler": lambda: manual_event_ingest(source="whatsapp"),
        "help": "Log a WhatsApp message as a work event (one-line summary)"
    },
}
