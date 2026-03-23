import asyncio
import json

from openai import AsyncAzureOpenAI, RateLimitError
from rich.console import Console

console = Console()

MAX_RETRIES = 5
RETRY_DELAYS = [5, 15, 30, 60, 120]  # seconds between retries


class AzureProvider:
    def __init__(self, api_key: str, endpoint: str, deployment: str, api_version: str):
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
        stream: bool = False,
    ) -> dict:
        kwargs = dict(
            model=self.model,
            messages=messages,
            tools=tools or None,
            tool_choice="auto" if tools else None,
        )
        return await self._complete_normal(kwargs)

    async def _complete_normal(self, kwargs: dict) -> dict:
        kwargs.pop("stream", None)
        kwargs.pop("stream_options", None)

        for attempt, delay in enumerate(RETRY_DELAYS + [None]):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                break
            except RateLimitError:
                if delay is None:
                    raise
                console.print(
                    f"[yellow]⚠ Rate limit, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})...[/yellow]"
                )
                await asyncio.sleep(delay)

        msg = response.choices[0].message if response.choices else None
        usage = response.usage

        if not msg:
            # Empty response from Azure — treat as empty content, no tool calls
            return {
                "content": "",
                "tool_calls": [],
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0,
                "reasoning": None,
            }

        reasoning = getattr(msg, "reasoning_content", None)
        if reasoning:
            console.print(f"[dim]🧠 {reasoning}[/dim]")
            console.print()

        return {
            "content": msg.content or "",
            "tool_calls": msg.tool_calls or [],
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
            "reasoning": reasoning,
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
