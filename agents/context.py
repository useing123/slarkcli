from __future__ import annotations

import json
import logging
from typing import Any

from providers.base import BaseProvider

logger = logging.getLogger(__name__)

PRUNE_THRESHOLD = 80_000
MAX_CONTEXT_TOKENS = 163_840
MIN_TOOL_CONTENT_LEN = 500
PREVIEW_LEN = 200


def _estimate_tokens(ctx: list[dict[str, Any]]) -> int:
    return sum(len((msg.get("content") or "")) // 4 for msg in ctx)


def _strip_code_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return raw


def _find_candidates(ctx: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for msg in ctx:
        if msg.get("role") != "tool":
            continue

        content = msg.get("content") or ""
        if len(content) <= MIN_TOOL_CONTENT_LEN:
            continue

        tool_call_id = msg.get("tool_call_id")
        if not tool_call_id:
            continue

        candidates.append(
            {
                "tool_call_id": tool_call_id,
                "preview": content[:PREVIEW_LEN],
                "length": len(content),
            }
        )

    return candidates


def _build_prompt(
    current_task: str, estimated: int, candidates: list[dict[str, Any]]
) -> str:
    return f"""You are a context manager for an AI coding agent.

Current task: {current_task or "unknown"}
Estimated context size: {estimated} tokens (limit: {MAX_CONTEXT_TOKENS})

These tool results are in the context. Decide which ones can be cleared
because the agent has already used their content and no longer needs them.

Tool results:
{json.dumps(candidates, indent=2, ensure_ascii=False)}

Return ONLY a JSON array of tool_call_ids to clear.
Example: ["call_abc", "call_xyz"]

If nothing should be cleared, return: []
"""


def _parse_tool_ids(raw: str) -> list[str]:
    raw = _strip_code_fences(raw)
    value = json.loads(raw)

    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, str) and item]


def _apply_prune(
    ctx: list[dict[str, Any]], to_clear: set[str]
) -> tuple[list[dict[str, Any]], int]:
    new_ctx: list[dict[str, Any]] = []
    cleared = 0

    for msg in ctx:
        if msg.get("role") == "tool" and msg.get("tool_call_id") in to_clear:
            tool_id = msg["tool_call_id"]
            new_ctx.append(
                {
                    **msg,
                    "content": json.dumps(
                        {
                            "status": "cleared",
                            "reason": "context_manager_pruned",
                            "tool_call_id": tool_id,
                        },
                        ensure_ascii=False,
                    ),
                }
            )
            cleared += 1
        else:
            new_ctx.append(msg)

    return new_ctx, cleared


async def prune(
    ctx: list[dict[str, Any]],
    provider: BaseProvider,
    current_task: str = "",
) -> list[dict[str, Any]]:
    estimated = _estimate_tokens(ctx)
    if estimated < PRUNE_THRESHOLD:
        return ctx

    candidates = _find_candidates(ctx)
    if not candidates:
        return ctx

    prompt = _build_prompt(current_task, estimated, candidates)

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        tools=[],
        stream=False,
    )

    raw = (getattr(response, "content", "") or "").strip()
    if not raw:
        return ctx

    try:
        to_clear = _parse_tool_ids(raw)
    except (json.JSONDecodeError, ValueError, IndexError):
        return ctx

    if not to_clear:
        return ctx

    new_ctx, cleared = _apply_prune(ctx, set(to_clear))
    if cleared:
        logger.info(
            "context manager cleared %s tool results (%s → ~%s est. tokens)",
            cleared,
            estimated,
            _estimate_tokens(new_ctx),
        )

    return new_ctx
