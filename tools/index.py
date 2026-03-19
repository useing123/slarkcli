import ast
import json
import re
from pathlib import Path

import aiosqlite

from memory.database import DB_PATH
from tools.read import ALWAYS_IGNORE, load_ignore_spec


async def init_index():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS symbols (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_dir TEXT NOT NULL,
                file        TEXT NOT NULL,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL,
                line        INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS imports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_dir TEXT NOT NULL,
                file        TEXT NOT NULL,
                imports     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS project_index_meta (
                project_dir TEXT PRIMARY KEY,
                indexed_at  TEXT NOT NULL,
                file_count  INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
            CREATE INDEX IF NOT EXISTS idx_symbols_project ON symbols(project_dir);
        """)
        await db.commit()


def _parse_python(file: Path, rel: str) -> list[dict]:
    symbols = []
    try:
        tree = ast.parse(file.read_text(errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(
                    {
                        "file": rel,
                        "name": node.name,
                        "type": "function",
                        "line": node.lineno,
                    }
                )
            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    {
                        "file": rel,
                        "name": node.name,
                        "type": "class",
                        "line": node.lineno,
                    }
                )
    except SyntaxError:
        pass
    return symbols


def _parse_ts_js(file: Path, rel: str) -> list[dict]:
    symbols = []
    patterns = [
        (r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)", "function"),
        (r"^(?:export\s+)?class\s+(\w+)", "class"),
        (r"^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(", "function"),
        (
            r"^(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?function",
            "function",
        ),
        (r"^(?:export\s+)?interface\s+(\w+)", "interface"),
        (r"^(?:export\s+)?type\s+(\w+)\s*=", "type"),
    ]
    try:
        lines = file.read_text(errors="replace").splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            for pattern, kind in patterns:
                m = re.match(pattern, stripped)
                if m:
                    symbols.append(
                        {
                            "file": rel,
                            "name": m.group(1),
                            "type": kind,
                            "line": i,
                        }
                    )
                    break
    except Exception:
        pass
    return symbols


def _parse_imports(file: Path, rel: str, ext: str) -> list[str]:
    imports = []
    try:
        content = file.read_text(errors="replace")
        if ext == ".py":
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
        else:
            for m in re.finditer(r'(?:import|from)\s+["\']([^"\']+)["\']', content):
                imports.append(m.group(1))
    except Exception:
        pass
    return imports


async def build(working_dir: Path) -> dict:
    from datetime import datetime

    await init_index()
    spec = load_ignore_spec(working_dir)
    project_dir = str(working_dir)

    SUPPORTED = {".py", ".ts", ".tsx", ".js", ".jsx"}

    all_symbols = []
    all_imports = []
    file_count = 0

    for f in sorted(working_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = str(f.relative_to(working_dir))
        if spec.match_file(rel):
            continue
        ext = f.suffix.lower()
        if ext not in SUPPORTED:
            continue

        file_count += 1

        if ext == ".py":
            all_symbols += _parse_python(f, rel)
        elif ext in {".ts", ".tsx", ".js", ".jsx"}:
            all_symbols += _parse_ts_js(f, rel)

        imports = _parse_imports(f, rel, ext)
        if imports:
            all_imports.append((project_dir, rel, json.dumps(imports)))

    async with aiosqlite.connect(DB_PATH) as db:
        # clear old index for this project
        await db.execute("DELETE FROM symbols WHERE project_dir = ?", (project_dir,))
        await db.execute("DELETE FROM imports WHERE project_dir = ?", (project_dir,))

        # insert symbols
        await db.executemany(
            "INSERT INTO symbols (project_dir, file, name, type, line) VALUES (?, ?, ?, ?, ?)",
            [
                (project_dir, s["file"], s["name"], s["type"], s["line"])
                for s in all_symbols
            ],
        )

        # insert imports
        await db.executemany(
            "INSERT INTO imports (project_dir, file, imports) VALUES (?, ?, ?)",
            all_imports,
        )

        # update meta
        await db.execute(
            "INSERT OR REPLACE INTO project_index_meta (project_dir, indexed_at, file_count) VALUES (?, ?, ?)",
            (project_dir, datetime.now().isoformat(), file_count),
        )
        await db.commit()

    return {
        "files": file_count,
        "symbols": len(all_symbols),
    }


async def search_symbol(name: str, working_dir: Path) -> str:
    project_dir = str(working_dir)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT file, name, type, line FROM symbols WHERE project_dir = ? AND name LIKE ? ORDER BY file",
            (project_dir, f"%{name}%"),
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return json.dumps(
            {
                "status": "error",
                "tool": "search_symbol",
                "reason": "not_found",
                "name": name,
            }
        )

    results = [
        {"file": r["file"], "name": r["name"], "type": r["type"], "line": r["line"]}
        for r in rows
    ]
    return json.dumps(
        {"status": "success", "tool": "search_symbol", "name": name, "results": results}
    )


async def get_file_symbols(path: str, working_dir: Path) -> str:
    project_dir = str(working_dir)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT name, type, line FROM symbols WHERE project_dir = ? AND file = ? ORDER BY line",
            (project_dir, path),
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return json.dumps(
            {
                "status": "error",
                "tool": "get_file_symbols",
                "reason": "not_found",
                "path": path,
            }
        )

    results = [{"name": r["name"], "type": r["type"], "line": r["line"]} for r in rows]
    return json.dumps(
        {
            "status": "success",
            "tool": "get_file_symbols",
            "path": path,
            "results": results,
        }
    )


async def index_summary(working_dir: Path) -> str:
    project_dir = str(working_dir)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT * FROM project_index_meta WHERE project_dir = ?", (project_dir,)
        ) as cursor:
            meta = await cursor.fetchone()

        async with db.execute(
            "SELECT type, COUNT(*) as count FROM symbols WHERE project_dir = ? GROUP BY type",
            (project_dir,),
        ) as cursor:
            types = await cursor.fetchall()

    if not meta:
        return json.dumps(
            {"status": "error", "tool": "index_summary", "reason": "not_indexed"}
        )

    return json.dumps(
        {
            "status": "success",
            "tool": "index_summary",
            "indexed_at": meta["indexed_at"],
            "file_count": meta["file_count"],
            "symbols": {r["type"]: r["count"] for r in types},
        }
    )


INDEX_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_symbol",
            "description": "Search for a function, class, or type by name across the entire project. Faster than grep for finding definitions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Symbol name to search for (partial match supported)",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_symbols",
            "description": "Get all functions and classes defined in a specific file.",
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
            "name": "index_summary",
            "description": "Show project index statistics — how many files and symbols are indexed.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]
