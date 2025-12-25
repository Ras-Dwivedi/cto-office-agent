# src/cli/commands.py

from src.work_logs.record_decisions import main as record_decision
from src.work_logs.generate_markdown import main as generate_markdown
from src.work_logs.pomodoro import main as pomodoro

COMMAND_ROUTES = {
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

}
