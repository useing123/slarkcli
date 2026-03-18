import json
import shutil
from datetime import datetime
from pathlib import Path

from tools.read import is_forbidden

GARBAGE_DIR = Path.home() / ".slark" / "garbage"


def _ok(tool: str, **kwargs) -> str:
    return json.dumps({"status": "success", "tool": tool, **kwargs})


def _err(tool: str, reason: str, **kwargs) -> str:
    return json.dumps({"status": "error", "tool": tool, "reason": reason, **kwargs})


def write_file(path: str, content: str, working_dir: Path) -> str:
    if is_forbidden(path):
        return _err("write_file", "forbidden", path=path)

    full = working_dir / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    return _ok(
        "write_file",
        path=path,
        lines=len(content.splitlines()),
        bytes=len(content.encode()),
    )


def str_replace(path: str, old_str: str, new_str: str, working_dir: Path) -> str:
    if is_forbidden(path):
        return _err("str_replace", "forbidden", path=path)

    full = working_dir / path
    if not full.exists():
        return _err("str_replace", "not_found", path=path)

    content = full.read_text(errors="replace")
    count = content.count(old_str)

    if count == 0:
        return _err("str_replace", "string_not_found", path=path)
    if count > 1:
        return _err("str_replace", "ambiguous_match", path=path, matches=count)

    new_content = content.replace(old_str, new_str, 1)
    full.write_text(new_content)

    line = content[: content.index(old_str)].count("\n") + 1
    return _ok("str_replace", path=path, line=line)


def create_dir(path: str, working_dir: Path) -> str:
    full = working_dir / path
    full.mkdir(parents=True, exist_ok=True)
    return _ok("create_dir", path=path)


def move_to_garbage(path: str, working_dir: Path, session_id: str) -> str:
    if is_forbidden(path):
        return _err("move_to_garbage", "forbidden", path=path)

    full = working_dir / path
    if not full.exists():
        return _err("move_to_garbage", "not_found", path=path)

    dest_dir = GARBAGE_DIR / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%H%M%S")
    dest = dest_dir / f"{timestamp}_{full.name}"

    shutil.move(str(full), dest)
    return _ok("move_to_garbage", path=path, saved_to=str(dest), recoverable=True)


# --- Tool schemas ---

EDIT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file, creates it if it doesn't exist",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "str_replace",
            "description": "Replace a specific string in a file. Must be unique in the file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_str": {
                        "type": "string",
                        "description": "Exact string to replace",
                    },
                    "new_str": {"type": "string", "description": "Replacement string"},
                },
                "required": ["path", "old_str", "new_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_dir",
            "description": "Create a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_to_garbage",
            "description": "Safely delete a file by moving it to garbage. Always use this instead of rm. Files are recoverable from ~/.slark/garbage/",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        },
    },
]
