from pathlib import Path

from agents.bootstrap import get_provider
from config import Config
from memory.database import (
    clear_session_messages,
    list_sessions,
    load_session,
    new_session,
)
from memory.history import History
from tools.index import build
from ui.settings import run_settings


async def handle_command(
    task: str,
    *,
    session_id: str,
    working_dir: Path,
    history: History,
    config: Config,
    provider,
    session_in: int,
    session_out: int,
):
    if task == "/clear":
        if session_id:
            await clear_session_messages(session_id)
        history.clear()
        return {"action": "clear"}

    if task == "/new":
        new_id = await new_session(working_dir)
        history.clear()
        return {"action": "new", "session_id": new_id}

    if task == "/cost":
        cost = session_in * config.price_in + session_out * config.price_out
        return {"action": "cost", "value": cost}

    if task == "/init":
        result = await build(working_dir)
        return {"action": "init", "value": result}

    if task == "/sessions":
        sessions = await list_sessions(str(working_dir))
        return {"action": "sessions", "value": sessions}

    if task.startswith("/switch "):
        arg = task.split(" ", 1)[1].strip()
        sessions = await list_sessions(str(working_dir))

        target = None
        if arg.isdigit():
            idx = int(arg) - 1
            if 0 <= idx < len(sessions):
                target = sessions[idx]
        else:
            target = next((s for s in sessions if s["id"].startswith(arg)), None)

        if not target:
            return {"action": "error", "value": f"Session not found: {arg}"}

        msgs = await load_session(target["id"])
        history.clear()
        for m in msgs:
            if m["role"] == "user":
                history.add_user(m["content"])
            elif m["role"] == "assistant":
                history.add_assistant(m["content"])

        return {
            "action": "switch",
            "session_id": target["id"],
            "value": {
                "messages": msgs,
                "created_at": target["created_at"],
                "message_count": len(msgs),
            },
        }

    if task == "/settings":
        new_config, changed = await run_settings(config)
        if not changed:
            return {
                "action": "settings",
                "changed": False,
                "config": config,
                "provider": provider,
            }

        try:
            new_provider = get_provider(new_config)
        except Exception as e:
            return {"action": "error", "value": f"Provider error: {e}"}

        return {
            "action": "settings",
            "changed": True,
            "config": new_config,
            "provider": new_provider,
        }

    return None
