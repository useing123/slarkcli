"""
In-memory registry of running workers.
Orchestrator uses this to track, read and kill agents.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum


class WorkerStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    KILLED = "killed"


@dataclass
class WorkerEntry:
    name: str
    session_id: str
    task: str
    status: WorkerStatus = WorkerStatus.PENDING
    result: str | None = None
    error: str | None = None
    asyncio_task: asyncio.Task | None = field(default=None, repr=False)
    logs: list[str] = field(default_factory=list)  # tool call log


class AgentRegistry:
    def __init__(self):
        self._workers: dict[str, WorkerEntry] = {}

    def register(self, entry: WorkerEntry):
        self._workers[entry.name] = entry

    def get(self, name: str) -> WorkerEntry | None:
        return self._workers.get(name)

    def list(self) -> list[WorkerEntry]:
        return list(self._workers.values())

    def remove(self, name: str):
        self._workers.pop(name, None)

    def all_done(self) -> bool:
        return all(
            w.status in (WorkerStatus.DONE, WorkerStatus.FAILED, WorkerStatus.KILLED)
            for w in self._workers.values()
        )


# Global registry shared between orchestrator and tool handlers
REGISTRY = AgentRegistry()
