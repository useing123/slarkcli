from providers.types import ToolCall, ToolCallFunction


def normalize_tool_calls(raw_calls) -> list[ToolCall]:
    if not raw_calls:
        return []

    result: list[ToolCall] = []

    for raw in raw_calls:
        result.append(
            ToolCall(
                id=getattr(raw, "id", ""),
                type="function",
                function=ToolCallFunction(
                    name=raw.function.name,
                    arguments=raw.function.arguments,
                ),
            )
        )

    return result
