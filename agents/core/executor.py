from pathlib import Path

from agents.core.messages import parse_tool_inputs
from tools.runtime.executor import execute_tool


async def execute_tool_calls(
    tool_calls, working_dir: Path, session_id: str, on_tool=None
):
    results = []

    for tc in tool_calls:
        name = tc.function.name
        inputs = parse_tool_inputs(tc.function.arguments)

        if on_tool:
            on_tool("start", name, inputs)

        result = await execute_tool(name, inputs, working_dir, session_id)

        if on_tool:
            on_tool("end", name, result)

        results.append((tc.id, result))

    return results
