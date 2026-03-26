import json
from pathlib import Path

from tools.registry import execute_tool as _execute_tool


async def execute_tool(
    name: str, inputs: dict, working_dir: Path, session_id: str
) -> str:
    try:
        result = await _execute_tool(name, inputs, working_dir, session_id)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        return json.dumps({"status": "error", "tool": name, "reason": str(e)})
