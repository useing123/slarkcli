from dataclasses import dataclass


@dataclass
class ToolCallFunction:
    name: str
    arguments: str


@dataclass
class ToolCall:
    id: str
    type: str
    function: ToolCallFunction


@dataclass
class ProviderResponse:
    content: str
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int
    reasoning: str | None = None
