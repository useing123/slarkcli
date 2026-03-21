from pathlib import Path

import aiosqlite

from config import Config
from memory.database import DB_PATH, close_abandoned_tasks, get_or_create_session, init
from memory.history import History
from tools.index import build, init_index


async def _cleanup_empty_sessions(working_dir: Path):
    """Delete empty sessions except the last one."""
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
    if config.provider == "azure":
        from providers.azure import AzureProvider

        if not config.azure_key or not config.azure_endpoint:
            raise ValueError(
                "Azure provider selected but azure.api_key or azure.endpoint missing.\n"
                "Run /settings to configure."
            )
        return AzureProvider(
            api_key=config.azure_key,
            endpoint=config.azure_endpoint,
            deployment=config.azure_deployment,
            api_version=config.azure_api_version,
        )

    if config.provider == "openrouter":
        from providers.openrouter import OpenRouterProvider

        return OpenRouterProvider(api_key=config.openrouter_key, model=config.model)

    raise ValueError(f"Unknown provider: {config.provider}")


async def bootstrap(working_dir: Path) -> dict:
    config = Config.load()

    needs_setup = (config.provider == "openrouter" and not config.openrouter_key) or (
        config.provider == "azure"
        and (not config.azure_key or not config.azure_endpoint)
    )
    if needs_setup:
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
