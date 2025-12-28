#!/usr/bin/env python3

import argparse
import sys

from src.commands.commands import COMMAND_ROUTES


def main():
    parser = argparse.ArgumentParser(
        prog="workctl",
        description="CTO Office Control Tool"
    )

    # =====================================================
    # SHORTCUT FLAGS
    # =====================================================

    parser.add_argument(
        "-p", "--pomodoro",
        action="store_true",
        help="Start a live Pomodoro session"
    )

    parser.add_argument(
        "-pl", "--pomodoro-log",
        action="store_true",
        help="Log past work (no timer)"
    )

    parser.add_argument(
        "-t", "--priority",
        action="store_true",
        help="Show top priority tasks"
    )

    # -------- Interrupt shortcuts --------
    parser.add_argument(
        "-c", "--call",
        action="store_true",
        help="Log a phone call as a work event"
    )

    parser.add_argument(
        "-w", "--whatsapp",
        action="store_true",
        help="Log a WhatsApp message as a work event"
    )

    # =====================================================
    # COMMAND (fallback)
    # =====================================================
    parser.add_argument(
        "command",
        nargs="?",
        help="Command to run"
    )

    args = parser.parse_args()

    # =====================================================
    # SHORTCUT RESOLUTION (highest priority)
    # =====================================================

    if args.pomodoro:
        COMMAND_ROUTES["pomodoro-live"]["handler"]()
        return

    if args.pomodoro_log:
        COMMAND_ROUTES["pomodoro-log"]["handler"]()
        return

    if args.priority:
        COMMAND_ROUTES["priority"]["handler"]()
        return

    if args.call:
        COMMAND_ROUTES["call"]["handler"]()
        return

    if args.whatsapp:
        COMMAND_ROUTES["wa"]["handler"]()
        return

    # =====================================================
    # NORMAL COMMAND FLOW
    # =====================================================

    if not args.command:
        parser.print_help()
        return

    if args.command not in COMMAND_ROUTES:
        print(f"Unknown command: {args.command}")
        print("\nAvailable commands:")
        for cmd, meta in COMMAND_ROUTES.items():
            print(f"  {cmd:18} {meta['help']}")
        sys.exit(1)

    COMMAND_ROUTES[args.command]["handler"]()


if __name__ == "__main__":
    main()
