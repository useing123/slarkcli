import json
from pathlib import Path

from tools.runtime.registry import get_tool


async def execute_tool(
    name: str, inputs: dict, working_dir: Path, session_id: str
) -> str:
    handler = get_tool(name)

    if handler is None:
        return json.dumps(
            {
                "status": "error",
                "reason": f"Unknown tool {name}",
            }
        )

    try:
        return await handler(inputs, working_dir, session_id)
    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "tool": name,
                "reason": str(e),
            }
        )
