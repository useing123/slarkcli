from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

ToolHandler = Callable[[dict[str, Any], Path, str], Awaitable[str]]

TOOL_HANDLERS: dict[str, ToolHandler] = {}


def register_tool(name: str):
    def decorator(fn: ToolHandler) -> ToolHandler:
        if name in TOOL_HANDLERS:
            raise ValueError(f"Tool already registered: {name}")
        TOOL_HANDLERS[name] = fn
        return fn

    return decorator


def get_tool(name: str) -> ToolHandler | None:
    return TOOL_HANDLERS.get(name)


def list_tools() -> list[str]:
    return sorted(TOOL_HANDLERS)
