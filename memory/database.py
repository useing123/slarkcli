import json
import uuid
from datetime import datetime
from pathlib import Path

import aiosqlite

DB_PATH = Path.home() / ".slark" / "slark.db"


async def init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                project_dir TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                title       TEXT NOT NULL,
                description TEXT,
                status      TEXT DEFAULT 'pending',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dataset (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                messages   TEXT NOT NULL,
                rating     INTEGER,
                created_at TEXT NOT NULL
            );
        """)
        await db.commit()


async def new_session(working_dir: Path) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sessions (id, project_dir, created_at) VALUES (?, ?, ?)",
            (session_id, str(working_dir), now),
        )
        await db.commit()

    return session_id


async def save_message(session_id: str, role: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat()),
        )
        await db.commit()


async def save_to_dataset(
    session_id: str, messages: list[dict], rating: int | None = None
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO dataset (session_id, messages, rating, created_at) VALUES (?, ?, ?, ?)",
            (session_id, json.dumps(messages), rating, datetime.now().isoformat()),
        )
        await db.commit()


async def close_abandoned_tasks(project_dir: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE tasks SET status = 'abandoned'
            WHERE status IN ('pending', 'in_progress')
            AND session_id IN (
                SELECT id FROM sessions WHERE project_dir = ?
            )
        """,
            (project_dir,),
        )
        await db.commit()
