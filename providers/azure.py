import asyncio
import json
import re
from typing import Sequence

from openai import AsyncAzureOpenAI, RateLimitError

from providers.types import ProviderResponse
from providers.utils import normalize_tool_calls

RETRY_DELAYS = [5, 15, 30, 60, 120]

_RAW_TOOL_RE = re.compile(
    r"<｜tool▁call▁begin｜>function<｜tool▁sep｜>(\w+)\s*\njson\s*(\{.*?\})\s*(?:<｜tool▁call▁end｜>)?",
    re.DOTALL,
)


def _parse_raw_tool_calls(content: str) -> list[dict] | None:
    matches = _RAW_TOOL_RE.findall(content)
    if not matches:
        return None
    calls = []
    for i, (name, args_str) in enumerate(matches):
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {}
        calls.append(
            {
                "id": f"fallback_{i}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        )
    return calls


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
        messages: Sequence[dict],
        tools: Sequence[dict] | None,
        stream: bool = False,
    ) -> ProviderResponse:
        kwargs: dict = {
            "model": self.model,
            "messages": list(messages),
        }

        if tools:
            kwargs["tools"] = list(tools)
            kwargs["tool_choice"] = "auto"

        last_error = None

        for attempt, delay in enumerate(RETRY_DELAYS + [None]):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                break
            except RateLimitError as e:
                last_error = e
                if delay is None:
                    raise RuntimeError(
                        f"Rate limit exceeded after {attempt} retries"
                    ) from e
                await asyncio.sleep(delay)
        else:
            raise RuntimeError("Azure provider failed") from last_error

        msg = response.choices[0].message if response.choices else None
        usage = response.usage

        if not msg:
            return ProviderResponse(
                content="", tool_calls=[], input_tokens=0, output_tokens=0
            )

        content = msg.content or ""
        tool_calls = normalize_tool_calls(msg.tool_calls)

        if not tool_calls and content:
            raw = _parse_raw_tool_calls(content)
            if raw:
                tool_calls = normalize_tool_calls(raw)
                content = _RAW_TOOL_RE.sub("", content).strip()

        return ProviderResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            reasoning=getattr(msg, "reasoning_content", None),
        )
