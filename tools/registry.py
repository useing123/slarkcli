import asyncio
import inspect
from pathlib import Path

from tools.edit import create_dir, move_to_garbage, str_replace, write_file
from tools.index import get_file_symbols, index_summary, search_symbol
from tools.read import outline, read_file, read_lines, tree
from tools.run import (
    check_port,
    kill_background,
    kill_port,
    run_background,
    run_command,
)
from tools.search import find_definition, grep
from tools.tasks import create_task, list_tasks, update_task

SYNC_TOOLS = {
    "read_file": read_file,
    "read_lines": read_lines,
    "tree": tree,
    "outline": outline,
    "write_file": write_file,
    "str_replace": str_replace,
    "create_dir": create_dir,
    "grep": grep,
    "find_definition": find_definition,
    "run_command": run_command,
    "move_to_garbage": move_to_garbage,
    "run_background": run_background,
    "kill_background": kill_background,
    "check_port": check_port,
    "kill_port": kill_port,
}

ASYNC_TOOLS = {
    "search_symbol": search_symbol,
    "get_file_symbols": get_file_symbols,
    "index_summary": index_summary,
    "create_task": create_task,
    "update_task": update_task,
    "list_tasks": list_tasks,
}


def _inject(fn, inputs: dict, working_dir, session_id) -> dict:
    params = inspect.signature(fn).parameters
    inputs = dict(inputs)
    if "working_dir" in params:
        inputs["working_dir"] = working_dir
    if "session_id" in params:
        inputs["session_id"] = session_id
    return inputs


async def execute_tool(name: str, inputs: dict, working_dir, session_id) -> str:
    fn = SYNC_TOOLS.get(name) or ASYNC_TOOLS.get(name)

    if not fn:
        return f"Unknown tool: {name}"

    try:
        injected = _inject(fn, inputs, working_dir, session_id)
        if asyncio.iscoroutinefunction(fn):
            return await fn(**injected)
        return fn(**injected)
    except Exception as e:
        return f"Tool error: {name}: {e}"
