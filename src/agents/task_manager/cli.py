import sys

from src.agents.judgement.morning_brief import morning_judgement_brief
from src.agents.task_manager.task_state import (
    list_tasks,
    close_task,
    drop_task,
    start_task,
    wait_task,
    print_help,
    show_task,
)

def task_cli(*args):
    """
    task
    task list
    task close <id>
    task drop <id>
    task start <id>
    task wait <id>
    """

    argv = list(args) if args else sys.argv[2:]

    # -------------------------
    # Default: morning brief
    # -------------------------
    if not argv:
        morning_judgement_brief()
        return

    cmd = argv[0]

    # -------------------------
    # Subcommands
    # -------------------------
    if cmd == "list":
        list_tasks()
        return

    if cmd == "close" and len(argv) >= 2:
        close_task(argv[1])
        return

    if cmd == "drop" and len(argv) >= 2:
        drop_task(argv[1])
        return

    if cmd == "start" and len(argv) >= 2:
        start_task(argv[1])
        return

    if cmd == "wait" and len(argv) >= 2:
        wait_task(argv[1])
        return

    if cmd == "show" and len(argv) >= 2:
        show_task(argv[1])
        return
    print("❌ Invalid task command")
    print_help()
