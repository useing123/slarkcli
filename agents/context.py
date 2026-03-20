import json

from config import Config
from providers.base import BaseProvider

PRUNE_THRESHOLD = 80_000


def _estimate_tokens(ctx: list[dict]) -> int:
    total = 0
    for msg in ctx:
        content = msg.get("content") or ""
        total += len(content) // 4
    return total


async def prune(
    ctx: list[dict], provider: BaseProvider, current_task: str = ""
) -> list[dict]:
    estimated = _estimate_tokens(ctx)
    if estimated < PRUNE_THRESHOLD:
        return ctx

    candidates = []
    for i, msg in enumerate(ctx):
        if msg["role"] == "tool" and len(msg.get("content", "")) > 500:
            candidates.append(
                {
                    "index": i,
                    "tool_call_id": msg["tool_call_id"],
                    "preview": msg["content"][:200],
                }
            )

    if not candidates:
        return ctx

    prompt = f"""You are a context manager for an AI coding agent.
Current task: {current_task or "unknown"}
Estimated context size: {estimated} tokens (limit: 163840)

These tool results are in the context. Decide which ones can be cleared
because the agent has already used their content and no longer needs them.

Tool results:
{json.dumps(candidates, indent=2)}

Return ONLY a JSON array of tool_call_ids to clear. Example: ["call_abc", "call_xyz"]
If nothing should be cleared, return: []
"""

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        tools=[],
    )

    raw = response["content"].strip()

    try:
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        to_clear: list[str] = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return ctx

    if not to_clear:
        return ctx

    cleared = 0
    for msg in ctx:
        if msg["role"] == "tool" and msg.get("tool_call_id") in to_clear:
            tool_id = msg["tool_call_id"]
            msg["content"] = json.dumps(
                {
                    "status": "cleared",
                    "reason": "context_manager_pruned",
                    "tool_call_id": tool_id,
                }
            )
            cleared += 1

    print(
        f"  🧹 context manager: cleared {cleared} tool results ({estimated} → ~{_estimate_tokens(ctx)} est. tokens)"
    )
    return ctx
