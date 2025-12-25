#!/usr/bin/env python3
import sys
from src.commands.commands import COMMAND_ROUTES

def main():
    if len(sys.argv) < 2:
        print("\nAvailable commands:\n")
        for cmd in COMMAND_ROUTES:
            print(f"  {cmd}")
        sys.exit(0)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command not in COMMAND_ROUTES:
        print(f"\n❌ Unknown command: {command}")
        print("\nAvailable commands:")
        for cmd in COMMAND_ROUTES:
            print(f"  {cmd}")
        sys.exit(1)

    # Forward args to the command
    sys.argv = [command] + args
    COMMAND_ROUTES[command]()

if __name__ == "__main__":
    main()
