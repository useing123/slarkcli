"""
Orchestrator: PM agent that decomposes tasks and coordinates workers.
Does NOT write code itself — delegates everything via swarm tools.
Orchestrator model/provider are configured separately from worker model.
"""

import json
import os
from pathlib import Path

from config import Config
from memory.database import save_message
from providers.base import BaseProvider
from tools.swarm import (
    SWARM_TOOLS,
    kill_agent,
    list_agents,
    read_agent_session,
    spawn_agent,
    wait_agent,
)

DONE_SIGNAL = "[DONE]"
TRACE_DIR = Path.home() / ".slark" / "traces"

SYSTEM_PROMPT = """You are Slark Orchestrator — a senior engineering manager AI.

## Your role
You decompose tasks and coordinate worker agents. You NEVER write code or edit files yourself.

## How you work
You MUST use function calls (tools) to act. Never write JSON or tool calls as plain text.

Workflow:
1. Analyze the task
2. Call spawn_agent() for each subtask — use the actual function call, not text
3. Call wait_agent() to get results
4. Call read_agent_session() if you need to inspect what a worker did
5. Return a final summary ending with [DONE]

## Tool usage rules
- ALWAYS use function calls, never write {"name": "spawn_agent"} as plain text
- spawn_agent: give each agent a complete self-contained task with all needed context
- mode="parallel" — agents run concurrently (use for independent tasks)
- mode="sequential" — wait for completion before continuing (use when B depends on A)
- After parallel spawns, call wait_agent() for each one to collect results
- Call list_agents() to check status at any time

## Agent naming
Use descriptive names: "coder-1", "reviewer", "test-writer", "refactor-auth"

## Completion
When all work is done, end your final message with exactly: [DONE]
"""


def _build_orch_provider(cfg: Config):
    """Build provider for orchestrator based on orchestrator_provider config."""
    from agents.bootstrap import get_provider

    # Temporarily swap model/provider fields to build orchestrator's provider
    orch_cfg = Config(
        model=cfg.orchestrator_model,
        provider=cfg.orchestrator_provider,
        openrouter_key=cfg.openrouter_key,
        azure_key=cfg.azure_key,
        azure_endpoint=cfg.azure_endpoint,
        azure_deployment=cfg.orchestrator_model,  # deployment = model name for azure
        azure_api_version=cfg.azure_api_version,
    )
    return get_provider(orch_cfg)


async def _execute_swarm_tool(
    name: str,
    inputs: dict,
    provider: BaseProvider,
    working_dir: Path,
) -> str:
    match name:
        case "spawn_agent":
            return await spawn_agent(
                name=inputs["name"],
                task=inputs["task"],
                provider=provider,
                working_dir=working_dir,
                mode=inputs.get("mode", "parallel"),
            )
        case "wait_agent":
            return await wait_agent(inputs["name"])
        case "kill_agent":
            return await kill_agent(inputs["name"])
        case "list_agents":
            return list_agents()
        case "read_agent_session":
            return await read_agent_session(inputs["name"])
        case _:
            return json.dumps({"status": "error", "reason": f"unknown tool: {name}"})


async def _orch_loop(
    ctx: list[dict],
    orch_provider,
    worker_provider: BaseProvider,
    working_dir: Path,
    session_id: str,
    cfg: Config,
) -> tuple[str, int, int]:
    """Shared loop for both orchestrate() and orchestrate_turn()."""
    total_in, total_out = 0, 0
    iteration = 0

    while True:
        if os.getenv("SLARK_TRACE"):
            TRACE_DIR.mkdir(parents=True, exist_ok=True)
            (TRACE_DIR / f"orch_{session_id}_{iteration}.json").write_text(
                json.dumps(ctx, indent=2, ensure_ascii=False)
            )

        response = await orch_provider.complete(
            messages=ctx, tools=SWARM_TOOLS, stream=True
        )

        print(f"\n  🎯 {response['input_tokens']} in / {response['output_tokens']} out")

        total_in += response["input_tokens"]
        total_out += response["output_tokens"]
        iteration += 1

        content = response["content"] or ""

        if DONE_SIGNAL in content:
            result = content.replace(DONE_SIGNAL, "").strip()
            await save_message(session_id, "assistant", result)
            return result, total_in, total_out

        if not response["tool_calls"]:
            await save_message(session_id, "assistant", content)
            return content, total_in, total_out

        if iteration >= 30:
            return "Orchestrator: max iterations reached.", total_in, total_out

        ctx.append(
            {
                "role": "assistant",
                "content": content,
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
        )

        for tc in response["tool_calls"]:
            name = tc.function.name
            try:
                inputs = json.loads(tc.function.arguments)
                if not isinstance(inputs, dict):
                    inputs = {}
            except (json.JSONDecodeError, ValueError):
                inputs = {}

            print(f"  🎯 → {name}({list(inputs.keys())})")
            result = await _execute_swarm_tool(
                name, inputs, worker_provider, working_dir
            )
            ctx.append({"role": "tool", "tool_call_id": tc.id, "content": result})


async def orchestrate(
    user_task: str,
    provider: BaseProvider,
    working_dir: Path,
    session_id: str,
    config: Config = None,
) -> tuple[str, int, int]:
    cfg = config or Config.load()
    orch_provider = _build_orch_provider(cfg)

    print(
        f"\n  🎯 Orchestrator [{cfg.orchestrator_provider} / {cfg.orchestrator_model}]"
    )

    ctx = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_task},
    ]
    return await _orch_loop(ctx, orch_provider, provider, working_dir, session_id, cfg)


async def orchestrate_turn(
    messages: list[dict],
    provider: BaseProvider,
    working_dir: Path,
    session_id: str,
    config: Config = None,
) -> tuple[str, int, int]:
    cfg = config or Config.load()
    orch_provider = _build_orch_provider(cfg)

    # Replace worker system prompt with orchestrator system prompt
    ctx = [{"role": "system", "content": SYSTEM_PROMPT}] + [
        m for m in messages if m["role"] != "system"
    ]
    return await _orch_loop(ctx, orch_provider, provider, working_dir, session_id, cfg)
