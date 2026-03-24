import json
import subprocess
from pathlib import Path


def _ok(tool: str, **kwargs) -> str:
    return json.dumps({"status": "success", "tool": tool, **kwargs})


def _err(tool: str, reason: str, **kwargs) -> str:
    return json.dumps({"status": "error", "tool": tool, "reason": reason, **kwargs})


def _run(cmd: str, cwd: Path, timeout: int = 15) -> tuple[int, str]:
    r = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=timeout
    )
    return r.returncode, (r.stdout + r.stderr).strip()


def git_status(working_dir: Path) -> str:
    code, out = _run("git status --short", working_dir)
    if code != 0:
        return _err("git_status", out)
    return _ok("git_status", output=out or "clean")


def git_diff(path: str, working_dir: Path) -> str:
    target = f"-- {path}" if path else ""
    code, out = _run(f"git diff {target}", working_dir)
    if code != 0:
        return _err("git_diff", out)
    return _ok("git_diff", output=out or "no changes")


def git_log(n: int, working_dir: Path) -> str:
    code, out = _run(f"git log --oneline -{n}", working_dir)
    if code != 0:
        return _err("git_log", out)
    return _ok("git_log", output=out)


def git_checkout_file(path: str, working_dir: Path) -> str:
    code, out = _run(f"git checkout HEAD -- {path}", working_dir)
    if code != 0:
        return _err("git_checkout_file", out, path=path)
    return _ok("git_checkout_file", path=path)


def git_apply(patch: str, working_dir: Path) -> str:
    tmp = working_dir / ".slark_patch.diff"
    try:
        tmp.write_text(patch)
        code, out = _run(f"git apply --check {tmp}", working_dir)
        if code != 0:
            return _err("git_apply", "patch_rejected", reason=out)
        code, out = _run(f"git apply {tmp}", working_dir)
        if code != 0:
            return _err("git_apply", out)
        return _ok("git_apply", output=out or "applied")
    finally:
        tmp.unlink(missing_ok=True)


def git_show(ref: str, working_dir: Path) -> str:
    code, out = _run(f"git show {ref} --stat", working_dir)
    if code != 0:
        return _err("git_show", out, ref=ref)
    return _ok("git_show", output=out)


GIT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show working tree status (modified, staged, untracked files).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Show unstaged changes. Optionally for a specific file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path (optional)"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Show recent commit history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "description": "Number of commits (default 10)",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_checkout_file",
            "description": "Reset a file to HEAD state, discarding local changes.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_apply",
            "description": "Apply a unified diff patch string to the working tree.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patch": {"type": "string", "description": "Unified diff content"}
                },
                "required": ["patch"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_show",
            "description": "Show info about a commit or ref (stat only, no full diff).",
            "parameters": {
                "type": "object",
                "properties": {
                    "ref": {
                        "type": "string",
                        "description": "Commit hash, tag, or branch",
                    }
                },
                "required": ["ref"],
            },
        },
    },
]
