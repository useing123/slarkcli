"""
Swarm tools exposed to the orchestrator.
These are the only way the orchestrator interacts with workers.
"""

import asyncio
import json
from pathlib import Path

from memory.database import load_session, new_session
from providers.base import BaseProvider
from swarm.registry import REGISTRY, WorkerEntry, WorkerStatus


def _ok(tool: str, **kwargs) -> str:
    return json.dumps({"status": "success", "tool": tool, **kwargs})


def _err(tool: str, reason: str, **kwargs) -> str:
    return json.dumps({"status": "error", "tool": tool, "reason": reason, **kwargs})


async def spawn_agent(
    name: str,
    task: str,
    provider: BaseProvider,
    working_dir: Path,
    mode: str = "parallel",
) -> str:
    from swarm.worker import run_worker

    if REGISTRY.get(name):
        return _err("spawn_agent", "name_already_exists", name=name)

    session_id = await new_session(working_dir)
    entry = WorkerEntry(name=name, session_id=session_id, task=task)
    REGISTRY.register(entry)

    print(f"  🚀 spawning [{name}]  session={session_id[:8]}")

    coro = run_worker(name, task, provider, working_dir, session_id)

    if mode == "sequential":
        await coro
        return _ok(
            "spawn_agent",
            name=name,
            session_id=session_id,
            mode="sequential",
            status=entry.status,
            result=entry.result,
        )
    else:
        asyncio_task = asyncio.create_task(coro)
        entry.asyncio_task = asyncio_task
        return _ok("spawn_agent", name=name, session_id=session_id, mode="parallel")


async def wait_agent(name: str) -> str:
    entry = REGISTRY.get(name)
    if not entry:
        return _err("wait_agent", "not_found", name=name)
    if entry.asyncio_task and not entry.asyncio_task.done():
        await entry.asyncio_task
    return _ok(
        "wait_agent",
        name=name,
        status=entry.status,
        result=entry.result,
        error=entry.error,
    )


async def kill_agent(name: str) -> str:
    entry = REGISTRY.get(name)
    if not entry:
        return _err("kill_agent", "not_found", name=name)
    if entry.asyncio_task and not entry.asyncio_task.done():
        entry.asyncio_task.cancel()
    entry.status = WorkerStatus.KILLED
    return _ok("kill_agent", name=name)


def list_agents() -> str:
    workers = REGISTRY.list()
    if not workers:
        return _ok("list_agents", agents=[])
    agents = [
        {
            "name": w.name,
            "status": w.status,
            "session_id": w.session_id[:8],
            "task": w.task[:80],
            "result_preview": (w.result or "")[:120] if w.result else None,
            "error": w.error,
        }
        for w in workers
    ]
    return _ok("list_agents", agents=agents)


async def read_agent_session(name: str) -> str:
    entry = REGISTRY.get(name)
    if not entry:
        return _err("read_agent_session", "not_found", name=name)
    msgs = await load_session(entry.session_id)
    return _ok(
        "read_agent_session", name=name, session_id=entry.session_id[:8], messages=msgs
    )


SWARM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "spawn_agent",
            "description": "Spawn a worker agent to execute a task. mode=parallel returns immediately, mode=sequential waits for completion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Unique agent name e.g. 'coder-1', 'reviewer'",
                    },
                    "task": {
                        "type": "string",
                        "description": "Full self-contained task description",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["parallel", "sequential"],
                        "default": "parallel",
                    },
                },
                "required": ["name", "task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait_agent",
            "description": "Wait for a parallel agent to finish and get its result.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kill_agent",
            "description": "Cancel a running agent.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_agents",
            "description": "List all agents and their current status.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_agent_session",
            "description": "Read the full message history of an agent to see what it did.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
]
