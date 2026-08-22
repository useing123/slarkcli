import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

# Whole-word command/argument names, matched on word boundaries so e.g.
# "killtest.sh" or "npm run killtest" doesn't falsely match "kill".
BLACKLIST_WORDS = {
    "rm",
    "rmdir",
    "sudo",
    "su",
    "chmod",
    "chown",
    "dd",
    "mkfs",
    "fdisk",
    "wget",
    "ssh",
    "scp",
    "rsync",
    "shutdown",
    "reboot",
    "kill",
    "pkill",
}

# Shell-syntax patterns, matched as plain substrings (word boundaries don't
# apply to punctuation like this).
BLACKLIST_PATTERNS = {
    "> /dev/",
    "| bash",
}

_BLACKLIST_WORD_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in BLACKLIST_WORDS) + r")\b"
)

_background: dict[str, subprocess.Popen] = {}


def _ok(tool: str, **kwargs) -> str:
    return json.dumps({"status": "success", "tool": tool, **kwargs})


def _err(tool: str, reason: str, **kwargs) -> str:
    return json.dumps({"status": "error", "tool": tool, "reason": reason, **kwargs})


def _is_blacklisted(command: str) -> str | None:
    match = _BLACKLIST_WORD_RE.search(command)
    if match:
        return match.group(0)
    for term in BLACKLIST_PATTERNS:
        if term in command:
            return term
    return None


def _confirm(command: str, reason: str) -> bool:
    try:
        print(f"\n  ⚠️  Blacklisted command detected: '{reason}'")
        answer = input(f"  Run anyway: {command}\n  Allow? [y/N] ").strip().lower()
        return answer == "y"
    except (EOFError, KeyboardInterrupt):
        return False


def run_command(command: str, working_dir: Path, stdin_input: str = "") -> str:
    blocked = _is_blacklisted(command)
    if blocked:
        if not _confirm(command, blocked):
            return _err("run_command", "rejected_by_user", command=command)

    server_keywords = [
        "streamlit",
        "uvicorn",
        "flask",
        "fastapi",
        "npm start",
        "yarn dev",
        "python -m http",
    ]
    if any(kw in command for kw in server_keywords):
        return _err("run_command", "use_run_background", command=command)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=working_dir,
            timeout=30,
            input=stdin_input or None,
        )
        output = (result.stdout + result.stderr).strip()
        lines = output.splitlines()
        if len(lines) > 50:
            output = (
                "\n".join(lines[:50])
                + f"\n... ({len(lines) - 50} more lines, truncated)"
            )
        return _ok(
            "run_command",
            command=command,
            exit_code=result.returncode,
            output=output or "no output",
        )
    except subprocess.TimeoutExpired:
        return _err("run_command", "timeout", command=command)


def run_background(command: str, name: str, working_dir: Path) -> str:
    blocked = _is_blacklisted(command)
    if blocked:
        if not _confirm(f"{command} (background)", blocked):
            return _err("run_background", "rejected_by_user", command=command)

    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=working_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _background[name] = proc
    time.sleep(1)
    return _ok("run_background", name=name, pid=proc.pid)


def kill_background(name: str) -> str:
    proc = _background.get(name)
    if not proc:
        return _err("kill_background", "not_found", name=name)
    proc.send_signal(signal.SIGTERM)
    del _background[name]
    return _ok("kill_background", name=name)


def check_port(port: int) -> str:
    try:
        result = subprocess.run(
            f"curl -s -o /dev/null -w '%{{http_code}}' --connect-timeout 3 http://localhost:{port}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        code = result.stdout.strip()
        if code and code != "000":
            return _ok("check_port", port=port, http_code=code)
        return _err("check_port", "not_responding", port=port)
    except subprocess.TimeoutExpired:
        return _err("check_port", "timeout", port=port)


def kill_port(port: int) -> str:
    try:
        result = subprocess.run(
            f"lsof -ti:{port}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        pids = result.stdout.strip().splitlines()
        if not pids:
            return _err("kill_port", "not_found", port=port)

        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass

        return _ok("kill_port", port=port, killed_pids=pids)
    except subprocess.TimeoutExpired:
        return _err("kill_port", "timeout", port=port)


RUN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command. Dangerous commands require user confirmation. Do NOT use for servers — use run_background instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "stdin_input": {
                        "type": "string",
                        "description": "Optional stdin input to answer interactive prompts e.g. 'y\\n\\n\\n'",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_background",
            "description": "Start a long-running process in background (e.g. dev server).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "name": {
                        "type": "string",
                        "description": "Name to identify this process",
                    },
                },
                "required": ["command", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kill_background",
            "description": "Kill a background process by name.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_port",
            "description": "Check if a local server is running on a port.",
            "parameters": {
                "type": "object",
                "properties": {"port": {"type": "integer"}},
                "required": ["port"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kill_port",
            "description": "Kill any process occupying a specific port. Use this before starting a server if the port is already in use.",
            "parameters": {
                "type": "object",
                "properties": {"port": {"type": "integer"}},
                "required": ["port"],
            },
        },
    },
]
