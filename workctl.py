#!/usr/bin/env python3
import sys
from src.commands.commands import COMMAND_ROUTES

def print_global_help():
    print("\nAvailable commands:\n")
    for name, meta in COMMAND_ROUTES.items():
        print(f"  {name:<20} {meta.get('help', '')}")
    print("\nUse `workctl help <command>` for details.\n")

def print_command_help(command):
    meta = COMMAND_ROUTES.get(command)
    if not meta:
        print(f"\n❌ Unknown command: {command}\n")
        print_global_help()
        return

    print(f"\nCommand: {command}\n")
    print(meta.get("help", "No help available"))
    print("\nUsage:")
    print(f"  workctl {command} [options]\n")

def main():
    if len(sys.argv) < 2:
        print_global_help()
        sys.exit(0)

    command = sys.argv[1]
    args = sys.argv[2:]

    # Handle help explicitly
    if command == "help":
        if args:
            print_command_help(args[0])
        else:
            print_global_help()
        sys.exit(0)

    if command not in COMMAND_ROUTES:
        print(f"\n❌ Unknown command: {command}")
        print_global_help()
        sys.exit(1)

    # Forward remaining args
    sys.argv = [command] + args
    COMMAND_ROUTES[command]["handler"]()

if __name__ == "__main__":
    main()
