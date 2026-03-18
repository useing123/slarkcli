import json
import subprocess
from pathlib import Path

import pathspec

FORBIDDEN = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",
    "id_rsa",
    "id_ed25519",
    ".pem",
    ".key",
}

ALWAYS_IGNORE = [
    ".git",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".venv",
    "venv",
    ".env",
    "*.egg-info",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "node_modules",
    ".next",
    ".nuxt",
    "dist",
    "build",
    "*.min.js",
    "*.min.css",
    "target",
    "vendor",
    "*.class",
    "*.jar",
    ".gradle",
    "uv.lock",
    "package-lock.json",
    "yarn.lock",
    "Cargo.lock",
    "poetry.lock",
    "Gemfile.lock",
    ".idea",
    ".vscode",
    "*.suo",
    "*.user",
    ".DS_Store",
    "Thumbs.db",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.exe",
    "*.dll",
    "*.so",
    "*.dylib",
]

READ_LIMIT = 150


def _ok(tool: str, **kwargs) -> str:
    return json.dumps({"status": "success", "tool": tool, **kwargs})


def _err(tool: str, reason: str, **kwargs) -> str:
    return json.dumps({"status": "error", "tool": tool, "reason": reason, **kwargs})


def load_ignore_spec(working_dir: Path) -> pathspec.PathSpec:
    patterns = list(ALWAYS_IGNORE)
    gitignore = working_dir / ".gitignore"
    if gitignore.exists():
        patterns += gitignore.read_text().splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def is_forbidden(path: str) -> bool:
    name = Path(path).name
    return any(name == f or name.endswith(f) for f in FORBIDDEN)


def read_file(path: str, working_dir: Path) -> str:
    if is_forbidden(path):
        return _err("read_file", "forbidden", path=path)

    full = working_dir / path
    if not full.exists():
        return _err("read_file", "not_found", path=path)
    if not full.is_file():
        return _err("read_file", "not_a_file", path=path)

    lines = full.read_text(errors="replace").splitlines()
    total = len(lines)

    if total <= READ_LIMIT:
        return _ok("read_file", path=path, lines=total, content="\n".join(lines))

    preview = "\n".join(lines[:READ_LIMIT])
    return _ok(
        "read_file",
        path=path,
        lines=total,
        truncated=True,
        shown=READ_LIMIT,
        content=preview,
        hint="use read_lines(path, start, end) for specific sections or outline(path) to see structure",
    )


def read_lines(path: str, start: int, end: int, working_dir: Path) -> str:
    if is_forbidden(path):
        return _err("read_lines", "forbidden", path=path)

    full = working_dir / path
    if not full.exists():
        return _err("read_lines", "not_found", path=path)

    lines = full.read_text(errors="replace").splitlines()
    selected = lines[start - 1 : end]
    content = "\n".join(f"{start + i}: {line}" for i, line in enumerate(selected))
    return _ok("read_lines", path=path, start=start, end=end, content=content)


def tree(path: str, working_dir: Path, max_depth: int = 3) -> str:
    spec = load_ignore_spec(working_dir)
    root = working_dir / path
    dir_counts: dict[str, int] = {}
    dirs_seen: set[str] = set()

    for f in sorted(root.rglob("*")):
        rel = f.relative_to(working_dir)
        parts = rel.parts
        if spec.match_file(str(rel)):
            continue
        if f.is_file():
            parent = str(Path(*parts[:-1])) if len(parts) > 1 else "."
            dir_counts[parent] = dir_counts.get(parent, 0) + 1
        if f.is_dir() and len(parts) <= max_depth:
            dirs_seen.add(str(rel))

    dir_lines = []
    for d in sorted(dirs_seen):
        depth = len(Path(d).parts)
        indent = "  " * (depth - 1)
        count = dir_counts.get(d, 0)
        dir_lines.append(f"{indent}{d}/ ({count} files)")

    root_files = [
        str(f.relative_to(working_dir))
        for f in sorted(root.iterdir())
        if f.is_file() and not spec.match_file(str(f.relative_to(working_dir)))
    ]

    return _ok(
        "tree",
        path=path,
        max_depth=max_depth,
        total_dirs=len(dirs_seen),
        total_files=sum(dir_counts.values()),
        content="\n".join(root_files + dir_lines),
    )


OUTLINE_PATTERNS = {
    ".py": lambda line: line.strip().startswith(("def ", "async def ", "class ")),
    ".ts": lambda line: any(
        kw in line
        for kw in ("function ", "const ", "class ", "export ", "interface ", "type ")
    ),
    ".tsx": lambda line: any(
        kw in line
        for kw in ("function ", "const ", "class ", "export ", "interface ", "type ")
    ),
    ".js": lambda line: any(
        kw in line for kw in ("function ", "const ", "class ", "export ")
    ),
    ".jsx": lambda line: any(
        kw in line for kw in ("function ", "const ", "class ", "export ")
    ),
    ".go": lambda line: line.strip().startswith(("func ", "type ", "var ", "const ")),
    ".rs": lambda line: line.strip().startswith(
        ("fn ", "pub fn ", "struct ", "enum ", "impl ", "trait ")
    ),
}


def outline(path: str, working_dir: Path) -> str:
    if is_forbidden(path):
        return _err("outline", "forbidden", path=path)

    full = working_dir / path
    if not full.exists():
        return _err("outline", "not_found", path=path)

    ext = full.suffix.lower()
    matcher = OUTLINE_PATTERNS.get(ext)
    if not matcher:
        return _err("outline", "unsupported_language", path=path, ext=ext)

    lines = full.read_text(errors="replace").splitlines()
    result = [
        f"{i}: {line.rstrip()}"
        for i, line in enumerate(lines, 1)
        if matcher(line) and line.strip()
    ]

    return _ok(
        "outline",
        path=path,
        content="\n".join(result) if result else "No definitions found",
    )


READ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": f"Read file contents. Files over {READ_LIMIT} lines are truncated — use read_lines for specific sections or outline to see structure.",
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
            "name": "read_lines",
            "description": "Read specific lines from a file. Use after read_file hints truncation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start": {
                        "type": "integer",
                        "description": "Start line (1-indexed)",
                    },
                    "end": {"type": "integer", "description": "End line (inclusive)"},
                },
                "required": ["path", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tree",
            "description": "Show directory structure grouped by folders with file counts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": "."},
                    "max_depth": {
                        "type": "integer",
                        "default": 3,
                        "description": "Max directory depth to show",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outline",
            "description": "Show class and function definitions in a file. Supports .py, .ts, .tsx, .js, .jsx, .go, .rs",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
]
