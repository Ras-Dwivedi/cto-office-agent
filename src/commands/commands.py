from src.agents.task_manager.record_decisions import main as record_decision
from src.agents.task_manager.generate_markdown import main as generate_markdown
from src.agents.task_manager.pomodoro import main as pomodoro_main
from src.agents.task_manager.agent import main as email_task_creator
from src.agents.task_manager.priority_view import get_priority_task
from src.agents.judgement.morning_brief import morning_judgement_brief
from src.cli.open_email import open_email

# Manual event ingestion
from src.agents.task_manager.utils.manual_event_ingestion import main as manual_event_ingest


COMMAND_ROUTES = {

    # ========= WORK & DECISIONS =========
    "record-decision": {
        "handler": record_decision,
        "help": "Record a new decision (use --long for detailed entry)"
    },

    "generate-markdown": {
        "handler": generate_markdown,
        "help": "Generate Markdown report from all decisions"
    },

    # ========= WORK LOGGING =========
    "pomodoro": {
        "handler": lambda: pomodoro_main(mode="interactive"),
        "help": "Log work (interactive: pomodoro or past work)"
    },

    "pomodoro-live": {
        "handler": lambda: pomodoro_main(mode="live"),
        "help": "Start a live Pomodoro immediately"
    },

    "pomodoro-log": {
        "handler": lambda: pomodoro_main(mode="log"),
        "help": "Log past work (no timer)"
    },

    # ========= TASK CREATION =========
    "create-tasks": {
        "handler": email_task_creator,
        "help": "Read emails and create tasks automatically"
    },

    # ========= PRIORITY VIEW =========
    "priority": {
        "handler": get_priority_task,
        "help": "Show top 5 highest priority tasks"
    },

    # ========= MORNING BRIEF =========
    "morning": {
        "handler": morning_judgement_brief,
        "help": "Show morning judgment brief (delegate vs personal focus)"
    },

    # ========= EMAIL =========
    "open": {
        "handler": lambda task_id=None: open_email(task_id),
        "help": "Open the full email associated with a task_id"
    },

    # ========= MANUAL EVENT INGESTION =========
    "call": {
        "handler": lambda: manual_event_ingest(source="call"),
        "help": "Log a phone call as a work event (one-line summary)"
    },

    "wa": {
        "handler": lambda: manual_event_ingest(source="whatsapp"),
        "help": "Log a WhatsApp message as a work event (one-line summary)"
    },
}
