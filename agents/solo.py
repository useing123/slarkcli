import json
import os
from pathlib import Path

from agents.context import PRUNE_THRESHOLD, prune
from config import Config
from providers.base import BaseProvider
from tools.edit import EDIT_TOOLS, create_dir, move_to_garbage, str_replace, write_file
from tools.index import INDEX_TOOLS, get_file_symbols, index_summary, search_symbol
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

ALL_TOOLS = (
    READ_TOOLS + EDIT_TOOLS + SEARCH_TOOLS + RUN_TOOLS + TASK_TOOLS + INDEX_TOOLS
)

DONE_SIGNAL = "[DONE]"
TRACE_DIR = Path.home() / ".slark" / "traces"


def estimate_cost(
    input_tokens: int, output_tokens: int, config: Config = None
) -> float:
    cfg = config or Config.load()
    return input_tokens * cfg.price_in + output_tokens * cfg.price_out


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
        case "search_symbol":
            return await search_symbol(inputs["name"], working_dir)
        case "get_file_symbols":
            return await get_file_symbols(inputs["path"], working_dir)
        case "index_summary":
            return await index_summary(working_dir)
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
    provider: BaseProvider,
    messages: list[dict],
    working_dir: Path,
    session_id: str,
    config: Config = None,
    on_tool: callable = None,
    on_token: callable = None,
) -> tuple[str, int, int]:
    cfg = config or Config.load()
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

        if response.get("reasoning"):
            print(f"\n  🧠 thinking:\n{response['reasoning']}\n")

        if on_token:
            on_token(response["input_tokens"], response["output_tokens"], len(ctx))
        else:
            print(
                f"  📊 {response['input_tokens']} in / {response['output_tokens']} out | ctx={len(ctx)}"
            )

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
            if total_in > cfg.large_context:
                cost = estimate_cost(total_in, total_out, cfg)
                confirm = (
                    input(
                        f"\n⚠️  Large context ({total_in} tokens | ~${cost:.4f}). Continue? [y/N] "
                    )
                    .strip()
                    .lower()
                )
                if confirm != "y":
                    return "Stopped by user.", total_in, total_out
                iteration = 0
            else:
                return "Max iterations reached.", total_in, total_out

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

            if on_tool:
                on_tool(name, inputs)
            else:
                print(f"  🔧 {name}({inputs})")

            try:
                result = await execute(name, inputs, working_dir, session_id)
            except (KeyError, TypeError) as e:
                result = json.dumps(
                    {
                        "status": "error",
                        "tool": name,
                        "reason": f"invalid arguments: {e}",
                    }
                )

            ctx.append({"role": "tool", "tool_call_id": tc.id, "content": result})
