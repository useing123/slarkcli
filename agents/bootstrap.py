from pathlib import Path

import aiosqlite

from config import Config
from memory.database import DB_PATH, close_abandoned_tasks, get_or_create_session, init
from memory.history import History
from providers.openrouter import OpenRouterProvider
from tools.index import build, init_index


async def _cleanup_empty_sessions(working_dir: Path):
    """Удаляет пустые сессии проекта кроме последней."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT s.id FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            WHERE s.project_dir = ?
            GROUP BY s.id
            HAVING COUNT(m.id) = 0
            ORDER BY s.created_at DESC
            """,
            (str(working_dir),),
        ) as cursor:
            empty = [row[0] for row in await cursor.fetchall()]

        to_delete = empty[1:]
        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            await db.execute(
                f"DELETE FROM sessions WHERE id IN ({placeholders})", to_delete
            )
            await db.commit()


def get_provider(config: Config):
    if config.provider == "openrouter":
        return OpenRouterProvider(api_key=config.openrouter_key, model=config.model)
    raise ValueError(f"Unknown provider: {config.provider}")


async def bootstrap(working_dir: Path) -> dict:
    config = Config.load()

    if not config.openrouter_key:
        config = Config.setup_wizard()

    await init()
    await init_index()
    print("  🗺 indexing project...")
    result = await build(working_dir)
    print(f"  ✓ {result['files']} files, {result['symbols']} symbols indexed")
    await close_abandoned_tasks(str(working_dir))
    await _cleanup_empty_sessions(working_dir)

    session_id, msgs = await get_or_create_session(working_dir)

    history = History()
    for m in msgs:
        if m["role"] == "user":
            history.add_user(m["content"])
        elif m["role"] == "assistant":
            history.add_assistant(m["content"])

    provider = get_provider(config)

    return {
        "session_id": session_id,
        "provider": provider,
        "history": history,
        "config": config,
    }
