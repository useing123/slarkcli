from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam


class OpenRouterProvider:
    def __init__(self, api_key: str, model: str):
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            # default_headers={"X-Title": "Slark CLI"},
        )

    async def complete(
        self, messages: list[ChatCompletionMessageParam], tools: list[dict]
    ) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools or None,
            tool_choice="auto" if tools else None,
            extra_body={
                "provider": {
                    "data_collection": "deny",
                }
            },
        )

        msg = response.choices[0].message
        usage = response.usage

        return {
            "content": msg.content,
            "tool_calls": msg.tool_calls or [],
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
            "reasoning": getattr(msg, "reasoning_content", None),
        }
