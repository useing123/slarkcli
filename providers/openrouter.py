import asyncio
from typing import Sequence

from openai import AsyncAzureOpenAI, RateLimitError

from providers.types import ProviderResponse
from providers.utils import normalize_tool_calls

RETRY_DELAYS = [5, 15, 30, 60, 120]


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
        kwargs = dict(
            model=self.model,
            messages=list(messages),
            tools=list(tools) if tools else None,
            tool_choice="auto" if tools else None,
        )

        response = None

        for delay in RETRY_DELAYS + [None]:
            try:
                response = await self.client.chat.completions.create(**kwargs)
                break
            except RateLimitError:
                if delay is None:
                    raise
                await asyncio.sleep(delay)

        if response is None:
            raise RuntimeError("Azure provider failed")

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
