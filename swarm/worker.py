"""
Worker: a named agent that runs ask() with its own session and history.
"""

from pathlib import Path

from memory.database import new_session, save_message
from memory.history import History
from providers.base import BaseProvider
from swarm.registry import REGISTRY, WorkerEntry, WorkerStatus


async def run_worker(
    name: str,
    task: str,
    provider: BaseProvider,
    working_dir: Path,
    session_id: str,
) -> str:
    """Run ask() loop for a worker and update registry on completion."""
    from agents.solo import ask  # avoid circular import

    entry = REGISTRY.get(name)
    if not entry:
        return "worker not found in registry"

    entry.status = WorkerStatus.RUNNING

    history = History()
    history.add_user(task)
    await save_message(session_id, "user", task)

    def _on_tool(tool_name: str, inputs: dict):
        entry.logs.append(f"🔧 {tool_name}({inputs})")
        print(f"  [{name}] 🔧 {tool_name}")

    def _on_token(inp: int, out: int, ctx_len: int):
        print(f"  [{name}] 📊 {inp} in / {out} out | ctx={ctx_len}")

    try:
        answer, _, _ = await ask(
            provider=provider,
            messages=history.get(),
            working_dir=working_dir,
            session_id=session_id,
            on_tool=_on_tool,
            on_token=_on_token,
        )
        await save_message(session_id, "assistant", answer)
        entry.status = WorkerStatus.DONE
        entry.result = answer
        return answer
    except Exception as e:
        entry.status = WorkerStatus.FAILED
        entry.error = str(e)
        return f"error: {e}"
