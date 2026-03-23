from __future__ import annotations

import json
import os
from pathlib import Path

from agents.context import PRUNE_THRESHOLD, prune
from config import Config
from providers.base import BaseProvider
from tools.catalog import ALL_TOOLS
from tools.runtime import execute_tool

DONE_SIGNAL = "[DONE]"
TRACE_DIR = Path.home() / ".slark" / "traces"


def estimate_cost(
    input_tokens: int, output_tokens: int, config: Config = None
) -> float:
    cfg = config or Config.load()
    return input_tokens * cfg.price_in + output_tokens * cfg.price_out


def _trace_context(session_id: str, iteration: int, ctx: list[dict]) -> None:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    (TRACE_DIR / f"{session_id}_{iteration}.json").write_text(
        json.dumps(ctx, indent=2, ensure_ascii=False)
    )


def _parse_tool_inputs(raw: str) -> dict:
    try:
        inputs = json.loads(raw)
        if isinstance(inputs, dict):
            return inputs
    except Exception:
        pass
    return {}


def _build_assistant_message(response: dict) -> dict:
    return {
        "role": "assistant",
        "content": response["content"] or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in response["tool_calls"]
        ],
    }


async def _execute_tool_calls(
    tool_calls,
    working_dir: Path,
    session_id: str,
    on_tool=None,
):
    results = []

    for tc in tool_calls:
        name = tc.function.name
        inputs = _parse_tool_inputs(tc.function.arguments)

        if on_tool:
            on_tool("start", name, inputs)

        result = await execute_tool(name, inputs, working_dir, session_id)

        if on_tool:
            on_tool("end", name, result)

        results.append((tc.id, result))

    return results


async def ask(
    provider: BaseProvider,
    messages: list[dict],
    working_dir: Path,
    session_id: str,
    config: Config = None,
    on_tool: callable = None,
) -> tuple[str, int, int]:
    cfg = config or Config.load()
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
            _trace_context(session_id, iteration, ctx)

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

        ctx.append(_build_assistant_message(response))

        tool_results = await _execute_tool_calls(
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
