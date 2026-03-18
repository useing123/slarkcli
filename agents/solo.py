import json
import os
from pathlib import Path

from agents.context import PRUNE_THRESHOLD, prune
from agents.interrupt import InterruptHandler
from providers.openrouter import OpenRouterProvider
from tools.edit import EDIT_TOOLS, create_dir, move_to_garbage, str_replace, write_file
from tools.read import READ_TOOLS, outline, read_file, read_lines, tree
from tools.run import (
    RUN_TOOLS,
    check_port,
    kill_background,
    run_background,
    run_command,
)
from tools.search import SEARCH_TOOLS, find_definition, grep
from tools.tasks import TASK_TOOLS, create_task, list_tasks, update_task

ALL_TOOLS = READ_TOOLS + EDIT_TOOLS + SEARCH_TOOLS + RUN_TOOLS + TASK_TOOLS

PRICE_IN = 0.27 / 1_000_000
PRICE_OUT = 0.79 / 1_000_000
LARGE_CONTEXT = 50_000
DONE_SIGNAL = "[DONE]"
TRACE_DIR = Path.home() / ".slark" / "traces"


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return input_tokens * PRICE_IN + output_tokens * PRICE_OUT


async def execute(name: str, inputs: dict, working_dir: Path, session_id: str) -> str:
    match name:
        case "read_file":
            return read_file(inputs["path"], working_dir)
        case "read_lines":
            return read_lines(
                inputs["path"], inputs["start"], inputs["end"], working_dir
            )
        case "tree":
            return tree(inputs.get("path", "."), working_dir)
        case "outline":
            return outline(inputs["path"], working_dir)
        case "write_file":
            return write_file(inputs["path"], inputs["content"], working_dir)
        case "str_replace":
            return str_replace(
                inputs["path"], inputs["old_str"], inputs["new_str"], working_dir
            )
        case "create_dir":
            return create_dir(inputs["path"], working_dir)
        case "grep":
            return grep(inputs["pattern"], inputs.get("path", "."), working_dir)
        case "find_definition":
            return find_definition(inputs["name"], working_dir)
        case "run_command":
            return run_command(
                inputs["command"], working_dir, inputs.get("stdin_input", "")
            )
        case "move_to_garbage":
            return move_to_garbage(inputs["path"], working_dir, session_id)
        case "run_background":
            return run_background(inputs["command"], inputs["name"], working_dir)
        case "kill_background":
            return kill_background(inputs["name"])
        case "check_port":
            return check_port(inputs["port"])
        case "create_task":
            return await create_task(
                session_id, inputs["title"], inputs.get("description", "")
            )
        case "update_task":
            return await update_task(session_id, inputs["task_id"], inputs["status"])
        case "list_tasks":
            return await list_tasks(session_id)
        case _:
            return f"Unknown tool: {name}"


async def ask(
    provider: OpenRouterProvider,
    messages: list[dict],
    working_dir: Path,
    session_id: str,
    interrupt: InterruptHandler | None = None,
) -> tuple[str, int, int]:
    ctx = list(messages)
    total_in, total_out = 0, 0
    iteration = 0

    while True:
        if total_in > PRUNE_THRESHOLD:
            ctx = await prune(
                ctx, provider, current_task=messages[0].get("content", "")
            )

        if os.getenv("SLARK_TRACE"):
            TRACE_DIR.mkdir(parents=True, exist_ok=True)
            (TRACE_DIR / f"{session_id}_{iteration}.json").write_text(
                json.dumps(ctx, indent=2, ensure_ascii=False)
            )

        response = await provider.complete(messages=ctx, tools=ALL_TOOLS)
        print(f"  DEBUG: content={repr(response['content'])[:100]}")
        print(f"  DEBUG: tool_calls={len(response['tool_calls'])}")
        print(
            f"  DEBUG: reasoning={repr(response.get('reasoning'))[:100] if response.get('reasoning') else None}"
        )

        if response.get("reasoning"):
            print(f"\n  🧠 thinking:\n{response['reasoning']}\n")

        print(
            f"  📊 response tokens: in={response['input_tokens']} out={response['output_tokens']} ctx_msgs={len(ctx)}"
        )
        total_in += response["input_tokens"]
        total_out += response["output_tokens"]
        iteration += 1

        content = response["content"] or ""

        # check done signal
        if DONE_SIGNAL in content:
            clean = content.replace(DONE_SIGNAL, "").strip()
            return clean, total_in, total_out

        # no tool calls — agent finished without signal
        if not response["tool_calls"]:
            return content, total_in, total_out

        # check iteration limits
        max_iter = 10 if total_in > LARGE_CONTEXT else 20
        if iteration >= max_iter:
            if total_in > LARGE_CONTEXT:
                cost = estimate_cost(total_in, total_out)
                confirm = (
                    input(
                        f"\n⚠️  Large context ({total_in} tokens | ~${cost:.4f} so far). Continue? [y/N] "
                    )
                    .strip()
                    .lower()
                )
                if confirm != "y":
                    return "Stopped by user.", total_in, total_out
                iteration = 0
            else:
                return "Max iterations reached.", total_in, total_out

        # append assistant message
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

        # execute tools
        for tc in response["tool_calls"]:
            name = tc.function.name
            inputs = json.loads(tc.function.arguments)

            print(f"  🔧 {name}({inputs})")
            result = await execute(name, inputs, working_dir, session_id)

            ctx.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )
