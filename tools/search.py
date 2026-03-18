# search.py
import json
import subprocess
from pathlib import Path


def _ok(tool: str, **kwargs) -> str:
    return json.dumps({"status": "success", "tool": tool, **kwargs})


def _err(tool: str, reason: str, **kwargs) -> str:
    return json.dumps({"status": "error", "tool": tool, "reason": reason, **kwargs})


def grep(pattern: str, path: str, working_dir: Path) -> str:
    result = subprocess.run(
        ["grep", "-r", "-n", "--color=never", pattern, path],
        capture_output=True,
        text=True,
        cwd=working_dir,
    )
    lines = result.stdout.strip().splitlines()
    if not lines:
        return _err("grep", "no_matches", pattern=pattern, path=path)
    truncated = len(lines) > 50
    return _ok(
        "grep",
        pattern=pattern,
        matches=len(lines),
        truncated=truncated,
        results="\n".join(lines[:50]),
    )


def find_definition(name: str, working_dir: Path) -> str:
    patterns = [
        f"def {name}",
        f"class {name}",
        f"async def {name}",
        f"function {name}",
        f"const {name}",
        f"fn {name}",
    ]
    lines = []
    for pattern in patterns:
        result = subprocess.run(
            ["grep", "-r", "-n", "--color=never", pattern, "."],
            capture_output=True,
            text=True,
            cwd=working_dir,
        )
        if result.stdout.strip():
            lines += result.stdout.strip().splitlines()

    if not lines:
        return _err("find_definition", "not_found", name=name)
    return _ok("find_definition", name=name, results="\n".join(lines[:50]))


SEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search for a pattern in the codebase",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_definition",
            "description": "Find where a function or class is defined. Supports Python, JS/TS, Rust.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
]
