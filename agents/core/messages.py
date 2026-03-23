import json


def parse_tool_inputs(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def build_assistant_message(response: dict) -> dict:
    return {
        "role": "assistant",
        "content": response["content"] or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in response["tool_calls"]
        ],
    }
