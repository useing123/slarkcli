import json
import logging

from providers.types import ProviderResponse


def parse_tool_inputs(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError as e:
        logging.warning(f"Failed to parse tool inputs: {e}, raw={raw!r}")
        return {}


def build_assistant_message(response: ProviderResponse) -> dict:
    msg: dict = {
        "role": "assistant",
        "content": response.content or "",
    }
    if response.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in response.tool_calls
        ]
    return msg
