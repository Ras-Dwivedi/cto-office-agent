#!/usr/bin/env python3

import argparse
import sys

from src.commands.commands import COMMAND_ROUTES


def main():
    parser = argparse.ArgumentParser(
        prog="workctl",
        description="CTO Office Control Tool"
    )

    # ---- SHORTCUT FLAGS ----
    parser.add_argument(
        "-p", "--pomodoro",
        action="store_true",
        help="Start a Pomodoro session"
    )

    parser.add_argument(
        "-t", "--priority",
        action="store_true",
        help="Show top priority tasks"
    )

    # ---- COMMAND ----
    parser.add_argument(
        "command",
        nargs="?",
        help="Command to run"
    )

    args = parser.parse_args()

    # ---- SHORTCUT RESOLUTION ----
    if args.pomodoro:
        COMMAND_ROUTES["pomodoro"]["handler"]()
        return

    if args.priority:
        COMMAND_ROUTES["priority"]["handler"]()
        return

    # ---- NORMAL COMMAND FLOW ----
    if not args.command:
        parser.print_help()
        return

    if args.command not in COMMAND_ROUTES:
        print(f"Unknown command: {args.command}")
        print("Available commands:")
        for cmd, meta in COMMAND_ROUTES.items():
            print(f"  {cmd:15} {meta['help']}")
        sys.exit(1)

    COMMAND_ROUTES[args.command]["handler"]()


if __name__ == "__main__":
    main()
