import asyncio
from typing import Sequence

from openai import AsyncOpenAI, RateLimitError

from providers.types import ProviderResponse
from providers.utils import normalize_tool_calls

RETRY_DELAYS = [5, 15, 30, 60, 120]


class OpenRouterProvider:
    def __init__(self, api_key: str, model: str):
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
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
            "extra_body": {"data_collection": "deny"},
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
            raise RuntimeError("OpenRouter provider failed") from last_error

        msg = response.choices[0].message if response.choices else None
        usage = response.usage

        if not msg:
            return ProviderResponse(
                content="",
                tool_calls=[],
                input_tokens=0,
                output_tokens=0,
            )

        return ProviderResponse(
            content=msg.content or "",
            tool_calls=normalize_tool_calls(msg.tool_calls),
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            reasoning=getattr(msg, "reasoning_content", None),
        )
