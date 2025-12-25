# src/cli/commands.py

from src.work_logs.record_decisions import main as record_decision
from src.work_logs.generate_markdown import main as generate_markdown
from src.work_logs.pomodoro import main as pomodoro
#
# COMMAND_ROUTES = {
#     "record-decision": record_decision,
#     "generate-markdown": generate_markdown,
#     "pomodoro": pomodoro,
# }

COMMAND_ROUTES = {
    "record-decision": (record_decision, "Log a decision"),
    "pomodoro": (pomodoro, "Start a pomodoro session"),
    "generate-markdown": (generate_markdown, "Generates markdown for the decisions recorded"),
}
