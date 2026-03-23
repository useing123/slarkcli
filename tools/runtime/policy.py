from pathlib import Path

ALLOWED_COMMAND_PREFIXES = [
    "ls",
    "cat",
    "grep",
    "git",
    "npm",
    "pnpm",
    "python",
]


def is_command_allowed(command: str) -> bool:
    if not command:
        return False

    first = command.strip().split(" ")[0]

    return any(first == prefix for prefix in ALLOWED_COMMAND_PREFIXES)
