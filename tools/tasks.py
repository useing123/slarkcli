import json
from datetime import datetime
from pathlib import Path

import aiosqlite

from memory.database import DB_PATH


def _ok(tool: str, **kwargs) -> str:
    return json.dumps({"status": "success", "tool": tool, **kwargs})


def _err(tool: str, reason: str, **kwargs) -> str:
    return json.dumps({"status": "error", "tool": tool, "reason": reason, **kwargs})


async def _get_next_task_id(db, project_dir: str) -> int:
    async with db.execute(
        "SELECT COALESCE(MAX(task_id), 0) + 1 FROM tasks WHERE project_dir = ?",
        (project_dir,),
    ) as cursor:
        row = await cursor.fetchone()
        return row[0]


async def create_task(project_dir: str, title: str, description: str = "") -> str:
    now = datetime.now().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        task_id = await _get_next_task_id(db, project_dir)

        await db.execute(
            """INSERT INTO tasks
               (project_dir, task_id, title, description, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
            (project_dir, task_id, title, description, now, now),
        )
        await db.commit()

    return _ok("create_task", task_id=task_id, title=title, status="pending")


async def update_task(project_dir: str, task_id: int, status: str) -> str:
    if status not in ("pending", "in_progress", "done", "failed", "abandoned"):
        return _err("update_task", "invalid_status", status=status)

    now = datetime.now().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        result = await db.execute(
            """UPDATE tasks
               SET status = ?, updated_at = ?
               WHERE project_dir = ? AND task_id = ?""",
            (status, now, project_dir, task_id),
        )
        await db.commit()

        if result.rowcount == 0:
            return _err("update_task", "task_not_found", task_id=task_id)

    return _ok("update_task", task_id=task_id, status=status)


async def list_tasks(project_dir: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT task_id, title, status
               FROM tasks
               WHERE project_dir = ?
               ORDER BY task_id""",
            (project_dir,),
        ) as cursor:
            rows = await cursor.fetchall()

    tasks = [
        {
            "task_id": r["task_id"],
            "title": r["title"],
            "status": r["status"],
        }
        for r in rows
    ]

    return _ok("list_tasks", tasks=tasks)


async def clear_tasks(project_dir: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM tasks WHERE project_dir = ?",
            (project_dir,),
        )
        await db.commit()

    return _ok("clear_tasks")


async def close_abandoned_tasks(project_dir: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE tasks
               SET status = 'abandoned'
               WHERE project_dir = ?
               AND status IN ('pending', 'in_progress')""",
            (project_dir,),
        )
        await db.commit()


TASK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a task for current project",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update task status",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "status": {
                        "type": "string",
                        "enum": [
                            "pending",
                            "in_progress",
                            "done",
                            "failed",
                            "abandoned",
                        ],
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
            "description": "List all tasks for project",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_tasks",
            "description": "Delete all tasks for project",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
