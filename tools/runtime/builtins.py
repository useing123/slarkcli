from __future__ import annotations

from tools.edit import create_dir, move_to_garbage, str_replace, write_file
from tools.index import get_file_symbols, index_summary, search_symbol
from tools.read import outline, read_file, read_lines, tree
from tools.run import check_port, kill_background, run_background, run_command
from tools.runtime.registry import register_tool
from tools.search import find_definition, grep
from tools.tasks import create_task, list_tasks, update_task
from tools.git import git_status, git_diff, git_log, git_checkout_file, git_apply, git_show

@register_tool("read_file")
async def _read_file(inputs, working_dir, session_id):
    return read_file(inputs["path"], working_dir)


@register_tool("read_lines")
async def _read_lines(inputs, working_dir, session_id):
    return read_lines(inputs["path"], inputs["start"], inputs["end"], working_dir)


@register_tool("tree")
async def _tree(inputs, working_dir, session_id):
    return tree(inputs.get("path", "."), working_dir)


@register_tool("outline")
async def _outline(inputs, working_dir, session_id):
    return outline(inputs["path"], working_dir)


@register_tool("write_file")
async def _write_file(inputs, working_dir, session_id):
    return write_file(inputs["path"], inputs["content"], working_dir)


@register_tool("str_replace")
async def _str_replace(inputs, working_dir, session_id):
    return str_replace(
        inputs["path"], inputs["old_str"], inputs["new_str"], working_dir
    )


@register_tool("create_dir")
async def _create_dir(inputs, working_dir, session_id):
    return create_dir(inputs["path"], working_dir)


@register_tool("grep")
async def _grep(inputs, working_dir, session_id):
    return grep(inputs["pattern"], inputs.get("path", "."), working_dir)


@register_tool("find_definition")
async def _find_definition(inputs, working_dir, session_id):
    return find_definition(inputs["name"], working_dir)


@register_tool("run_command")
async def _run_command(inputs, working_dir, session_id):
    return run_command(inputs["command"], working_dir, inputs.get("stdin_input", ""))


@register_tool("move_to_garbage")
async def _move_to_garbage(inputs, working_dir, session_id):
    return move_to_garbage(inputs["path"], working_dir, session_id)


@register_tool("run_background")
async def _run_background(inputs, working_dir, session_id):
    return run_background(inputs["command"], inputs["name"], working_dir)


@register_tool("kill_background")
async def _kill_background(inputs, working_dir, session_id):
    return kill_background(inputs["name"])


@register_tool("check_port")
async def _check_port(inputs, working_dir, session_id):
    return check_port(inputs["port"])


@register_tool("search_symbol")
async def _search_symbol(inputs, working_dir, session_id):
    return await search_symbol(inputs["name"], working_dir)


@register_tool("get_file_symbols")
async def _get_file_symbols(inputs, working_dir, session_id):
    return await get_file_symbols(inputs["path"], working_dir)


@register_tool("index_summary")
async def _index_summary(inputs, working_dir, session_id):
    return await index_summary(working_dir)


@register_tool("create_task")
async def _create_task(inputs, working_dir, session_id):
    return await create_task(session_id, inputs["title"], inputs.get("description", ""))


@register_tool("update_task")
async def _update_task(inputs, working_dir, session_id):
    return await update_task(session_id, inputs["task_id"], inputs["status"])


@register_tool("list_tasks")
async def _list_tasks(inputs, working_dir, session_id):
    return await list_tasks(session_id)


@register_tool("git_status")
async def _git_status(inputs, working_dir, session_id):
    return git_status(working_dir)


@register_tool("git_diff")
async def _git_diff(inputs, working_dir, session_id):
    return git_diff(inputs.get("path", ""), working_dir)


@register_tool("git_log")
async def _git_log(inputs, working_dir, session_id):
    return git_log(inputs.get("n", 10), working_dir)


@register_tool("git_checkout_file")
async def _git_checkout_file(inputs, working_dir, session_id):
    return git_checkout_file(inputs["path"], working_dir)


@register_tool("git_apply")
async def _git_apply(inputs, working_dir, session_id):
    return git_apply(inputs["patch"], working_dir)


@register_tool("git_show")
async def _git_show(inputs, working_dir, session_id):
    return git_show(inputs["ref"], working_dir)
