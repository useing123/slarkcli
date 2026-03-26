from providers.types import ToolCall, ToolCallFunction


def normalize_tool_calls(raw_calls) -> list[ToolCall]:
    if not raw_calls:
        return []

    result: list[ToolCall] = []

    for raw in raw_calls:
        func = getattr(raw, "function", None)
        if func is None:
            continue
        result.append(
            ToolCall(
                id=getattr(raw, "id", ""),
                type="function",
                function=ToolCallFunction(
                    name=getattr(func, "name", ""),
                    arguments=getattr(func, "arguments", "{}"),
                ),
            )
        )

    return result
