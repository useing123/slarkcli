from openai import AsyncAzureOpenAI
from rich.console import Console

console = Console()


class AzureProvider:
    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str = "2024-12-01-preview",
    ):
        self.model = deployment
        self.client = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict],
        stream: bool = True,
    ) -> dict:
        kwargs = dict(
            model=self.model,
            messages=messages,
            tools=tools or None,
            tool_choice="auto" if tools else None,
        )

        if stream:
            return await self._complete_streaming(kwargs)
        else:
            return await self._complete_normal(kwargs)

    async def _complete_normal(self, kwargs: dict) -> dict:
        response = await self.client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        usage = response.usage
        return {
            "content": msg.content,
            "tool_calls": msg.tool_calls or [],
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
            "reasoning": getattr(msg, "reasoning_content", None),
        }

    async def _complete_streaming(self, kwargs: dict) -> dict:
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}

        content_chunks: list[str] = []
        reasoning_chunks: list[str] = []
        tool_calls_raw: dict[int, dict] = {}
        input_tokens = 0
        output_tokens = 0
        in_reasoning = False
        in_content = False

        stream = await self.client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.usage:
                input_tokens = chunk.usage.prompt_tokens or 0
                output_tokens = chunk.usage.completion_tokens or 0

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            reasoning_delta = getattr(delta, "reasoning_content", None)
            if reasoning_delta:
                if not in_reasoning:
                    console.print("\n  [dim]🧠[/dim] ", end="")
                    in_reasoning = True
                console.print(reasoning_delta, end="", markup=False)
                reasoning_chunks.append(reasoning_delta)

            if delta.content:
                if in_reasoning:
                    console.print("\n")
                    in_reasoning = False
                if not in_content:
                    in_content = True
                console.print(delta.content, end="", markup=False)
                content_chunks.append(delta.content)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_raw:
                        tool_calls_raw[idx] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    raw = tool_calls_raw[idx]
                    if tc_delta.id:
                        raw["id"] += tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            raw["function"]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            raw["function"]["arguments"] += tc_delta.function.arguments

        if in_content or in_reasoning:
            console.print()

        tool_calls = (
            [_ToolCall(raw) for raw in tool_calls_raw.values()]
            if tool_calls_raw
            else []
        )

        return {
            "content": "".join(content_chunks),
            "tool_calls": tool_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning": "".join(reasoning_chunks) if reasoning_chunks else None,
        }


class _ToolCallFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, raw: dict):
        self.id = raw["id"]
        self.type = "function"
        self.function = _ToolCallFunction(
            raw["function"]["name"],
            raw["function"]["arguments"],
        )
