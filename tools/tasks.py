# tasks.py
import json
from datetime import datetime

import aiosqlite

from memory.database import DB_PATH


def _ok(tool: str, **kwargs) -> str:
    return json.dumps({"status": "success", "tool": tool, **kwargs})


def _err(tool: str, reason: str, **kwargs) -> str:
    return json.dumps({"status": "error", "tool": tool, "reason": reason, **kwargs})


async def create_task(session_id: str, title: str, description: str = "") -> str:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO tasks (session_id, title, description, status, created_at, updated_at) VALUES (?, ?, ?, 'pending', ?, ?)",
            (session_id, title, description, now, now),
        )
        await db.commit()
        return _ok(
            "create_task", task_id=cursor.lastrowid, title=title, status="pending"
        )


async def update_task(session_id: str, task_id: int, status: str) -> str:
    if status not in ("pending", "in_progress", "done", "failed"):
        return _err("update_task", "invalid_status", status=status)
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ? AND session_id = ?",
            (status, now, task_id, session_id),
        )
        await db.commit()
    return _ok("update_task", task_id=task_id, status=status)


async def list_tasks(session_id: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, title, status, description FROM tasks WHERE session_id = ? ORDER BY id",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    if not rows:
        return _ok("list_tasks", tasks=[])
    tasks = [{"id": r["id"], "title": r["title"], "status": r["status"]} for r in rows]
    return _ok("list_tasks", tasks=tasks)


TASK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a task in your todo list before starting work",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short task title"},
                    "description": {
                        "type": "string",
                        "description": "Optional details",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update task status: pending → in_progress → done / failed",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "done", "failed"],
                    },
                },
                "required": ["task_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "Show current task list and progress",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
