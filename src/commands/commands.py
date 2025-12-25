# src/cli/commands.py

from src.work_logs.record_decisions import main as record_decision
from src.work_logs.generate_markdown import main as generate_markdown
from src.work_logs.pomodoro import main as pomodoro
from src.agents.task_creator.agent1 import main as email_task_creator
from src.agents.task_creator.priority_view import main as show_priority_tasks

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
        "handler": show_priority_tasks,
        "help": "Show top 5 highest priority tasks"
    },}
