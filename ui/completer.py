import re
from pathlib import Path

from prompt_toolkit.completion import Completer, Completion

COMMANDS = [
    "/cost",
    "/clear",
    "/new",
    "/init",
    "/sessions",
    "/switch",
    "/settings",
    "/exit",
    "/quit",
]


class SlarkCompleter(Completer):
    """Autocomplete: @filename and /commands."""

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir.resolve()

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        at_match = re.search(r"@([\w./\-]*)$", text)
        if at_match:
            typed = at_match.group(1)
            if "/" in typed:
                parts = typed.rsplit("/", 1)
                search_dir = self.working_dir / parts[0]
                name_prefix = parts[1]
            else:
                search_dir = self.working_dir
                name_prefix = typed

            if not search_dir.is_dir():
                return

            try:
                search_dir.relative_to(self.working_dir)
            except ValueError:
                return

            for entry in sorted(search_dir.iterdir()):
                if entry.name.startswith(".") or entry.name == "__pycache__":
                    continue
                if not entry.name.startswith(name_prefix):
                    continue

                try:
                    rel = entry.relative_to(self.working_dir)
                except ValueError:
                    continue

                is_dir = entry.is_dir()
                yield Completion(
                    str(rel) + ("/" if is_dir else ""),
                    start_position=-len(typed),
                    display=entry.name + ("/" if is_dir else ""),
                    display_meta="dir" if is_dir else entry.suffix or "file",
                )
            return

        if text.startswith("/"):
            for cmd in COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))
