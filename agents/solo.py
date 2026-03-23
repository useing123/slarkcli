from __future__ import annotations

import os
from pathlib import Path

from agents.context import PRUNE_THRESHOLD, prune
from agents.core.executor import execute_tool_calls
from agents.core.messages import build_assistant_message
from agents.core.trace import trace_context
from config import Config
from config.loader import load_config
from providers.base import BaseProvider
from tools.catalog import ALL_TOOLS

DONE_SIGNAL = "[DONE]"


def estimate_cost(
    input_tokens: int, output_tokens: int, config: Config = None
) -> float:
    cfg = config or load_config()
    return input_tokens * cfg.price_in + output_tokens * cfg.price_out


async def ask(
    provider: BaseProvider,
    messages: list[dict],
    working_dir: Path,
    session_id: str,
    config: Config = None,
    on_tool: callable = None,
) -> tuple[str, int, int]:
    cfg = config or load_config()
    ctx = list(messages)

    total_in, total_out = 0, 0
    iteration = 0

    while True:
        if total_in > PRUNE_THRESHOLD:
            ctx = await prune(
                ctx,
                provider,
                current_task=messages[0].get("content", "") if messages else "",
            )

        if os.getenv("SLARK_TRACE"):
            trace_context(session_id, iteration, ctx)

        response = await provider.complete(messages=ctx, tools=ALL_TOOLS, stream=False)

        total_in += response["input_tokens"]
        total_out += response["output_tokens"]
        iteration += 1

        content = response["content"] or ""

        if DONE_SIGNAL in content:
            return content.replace(DONE_SIGNAL, "").strip(), total_in, total_out

        if not response["tool_calls"]:
            return content, total_in, total_out

        max_iter = 10 if total_in > cfg.large_context else 20
        if iteration >= max_iter:
            return "Max iterations reached.", total_in, total_out

        ctx.append(build_assistant_message(response))

        tool_results = await execute_tool_calls(
            response["tool_calls"],
            working_dir,
            session_id,
            on_tool=on_tool,
        )

        for tool_id, result in tool_results:
            ctx.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": result,
                }
            )
