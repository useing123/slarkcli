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
        # Get next session-local task number
        async with db.execute(
            "SELECT COUNT(*) FROM tasks WHERE session_id = ?",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
            session_task_id = (row[0] or 0) + 1

        await db.execute(
            """INSERT INTO tasks
               (session_id, title, description, status, assigned_to, created_at, updated_at)
               VALUES (?, ?, ?, 'pending', ?, ?, ?)""",
            (session_id, title, description, str(session_task_id), now, now),
        )
        await db.commit()

    return _ok("create_task", task_id=session_task_id, title=title, status="pending")


async def update_task(session_id: str, task_id: int, status: str) -> str:
    if status not in ("pending", "in_progress", "done", "failed", "abandoned"):
        return _err("update_task", "invalid_status", status=status)

    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        # Match by session-local id stored in assigned_to
        result = await db.execute(
            """UPDATE tasks SET status = ?, updated_at = ?
               WHERE session_id = ? AND assigned_to = ?""",
            (status, now, session_id, str(task_id)),
        )
        await db.commit()
        if result.rowcount == 0:
            return _err("update_task", "task_not_found", task_id=task_id)

    return _ok("update_task", task_id=task_id, status=status)


async def list_tasks(session_id: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT assigned_to as task_id, title, status, description
               FROM tasks WHERE session_id = ?
               ORDER BY CAST(assigned_to AS INTEGER)""",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return _ok("list_tasks", tasks=[])

    tasks = [
        {
            "task_id": int(r["task_id"]),
            "title": r["title"],
            "status": r["status"],
        }
        for r in rows
    ]
    return _ok("list_tasks", tasks=tasks)


TASK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a task. Returns task_id starting from 1 for each new session.",
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
            "description": "Update task status using task_id from create_task or list_tasks response. pending → in_progress → done / failed",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "task_id exactly as returned by create_task or list_tasks",
                    },
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
            "description": "List all tasks for this session with their task_ids and statuses",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
