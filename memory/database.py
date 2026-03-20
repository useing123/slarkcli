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


async def get_or_create_session(working_dir: Path) -> tuple[str, list[dict]]:
    """
    Returns the last empty session of the project (if any) or creates a new one.
    Also returns the message history (empty for a new session).
    """
    project_dir = str(working_dir)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT s.id FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            WHERE s.project_dir = ?
            GROUP BY s.id
            HAVING COUNT(m.id) = 0
            ORDER BY s.created_at DESC
            LIMIT 1
            """,
            (project_dir,),
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            return row["id"], []

        async with db.execute(
            """
            SELECT s.id FROM sessions s
            JOIN messages m ON m.session_id = s.id
            WHERE s.project_dir = ?
            GROUP BY s.id
            ORDER BY s.created_at DESC
            LIMIT 1
            """,
            (project_dir,),
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            session_id = row["id"]
            async with db.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ) as cursor:
                msgs = [dict(r) for r in await cursor.fetchall()]
            return session_id, msgs

    session_id = await new_session(working_dir)
    return session_id, []


async def clear_session_messages(session_id: str):
    """Deletes all messages from the session from the database (the session remains)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await db.commit()


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


async def list_sessions(project_dir: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT s.id, s.created_at,
                   COUNT(m.id) as message_count
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            WHERE s.project_dir = ?
            GROUP BY s.id
            ORDER BY s.created_at DESC
            LIMIT 20
            """,
            (project_dir,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def load_session(session_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]
