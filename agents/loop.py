import asyncio
import re
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from rich.console import Console
from rich.markdown import Markdown

from agents.bootstrap import bootstrap
from agents.solo import ask, estimate_cost
from memory.database import (
    clear_session_messages,
    get_or_create_session,
    list_sessions,
    load_session,
    new_session,
    save_message,
    save_to_dataset,
)
from memory.history import History
from ui.banner import BANNER, GOODBYE

console = Console()

_MD_TRIGGERS = ["```", "**", "##", "- ", "* ", "1. "]

COMMANDS = [
    "/cost",
    "/clear",
    "/new",
    "/init",
    "/sessions",
    "/switch",
    "/exit",
    "/quit",
]


def _is_markdown(text: str) -> bool:
    return any(t in text for t in _MD_TRIGGERS)


def _render_answer(answer: str):
    if _is_markdown(answer):
        console.print(Markdown(answer))
    else:
        console.print(answer)


def _print_session_history(msgs: list[dict]):
    if not msgs:
        console.print("[dim]  (no messages)[/dim]")
        return
    for m in msgs:
        role = m["role"]
        content = m["content"]
        if role == "user":
            console.print(f"[bold cyan]>> {content}[/bold cyan]")
        else:
            console.print("[dim]┌─ assistant[/dim]")
            if _is_markdown(content):
                console.print(Markdown(content))
            else:
                console.print(content)
        console.print()


def _expand_file_refs(task: str, working_dir: Path) -> tuple[str, list[str]]:
    """Find @filename refs, read files, inject contents into the message."""
    pattern = re.compile(r"@([\w./\-]+)")
    refs = pattern.findall(task)

    if not refs:
        return task, []

    attached = []
    blocks = []

    for ref in refs:
        path = (working_dir / ref).resolve()

        try:
            path.relative_to(working_dir.resolve())
        except ValueError:
            console.print(f"[red]⚠ @{ref}: outside working directory, skipped[/red]")
            continue

        if not path.exists():
            console.print(f"[red]⚠ @{ref}: file not found[/red]")
            continue

        if not path.is_file():
            console.print(f"[red]⚠ @{ref}: not a file[/red]")
            continue

        try:
            content = path.read_text(errors="replace")
        except Exception as e:
            console.print(f"[red]⚠ @{ref}: read error — {e}[/red]")
            continue

        rel = path.relative_to(working_dir.resolve())
        blocks.append(f'<file path="{rel}">\n{content}\n</file>')
        attached.append(str(rel))
        console.print(f"[dim]  📎 {rel} ({len(content.splitlines())} lines)[/dim]")

    if not blocks:
        return task, []

    clean_task = pattern.sub("", task).strip()
    expanded = clean_task + "\n\n" + "\n\n".join(blocks)
    return expanded, attached


class SlarkCompleter(Completer):
    """
    Autocomplete:
    - @<prefix> → files/dirs inside working_dir matching prefix
    - /<prefix> → slash commands
    """

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir.resolve()

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # --- @filename completion ---
        at_match = re.search(r"@([\w./\-]*)$", text)
        if at_match:
            typed = at_match.group(1)  # what user typed after @

            # Determine which directory to list and what name prefix to filter by
            if "/" in typed:
                # e.g. "src/comp" → list inside working_dir/src/, filter by "comp"
                parts = typed.rsplit("/", 1)
                parent_rel = parts[0]
                name_prefix = parts[1]
                search_dir = self.working_dir / parent_rel
            else:
                # e.g. "src" → list working_dir root, filter by "src"
                search_dir = self.working_dir
                name_prefix = typed

            if not search_dir.is_dir():
                return

            # Safety: search_dir must be inside working_dir
            try:
                search_dir.relative_to(self.working_dir)
            except ValueError:
                return

            for entry in sorted(search_dir.iterdir()):
                if entry.name.startswith(".") or entry.name == "__pycache__":
                    continue
                if not entry.name.startswith(name_prefix):
                    continue

                try:
                    rel = entry.relative_to(self.working_dir)
                except ValueError:
                    continue

                is_dir = entry.is_dir()
                completion_text = str(rel) + ("/" if is_dir else "")

                yield Completion(
                    completion_text,
                    start_position=-len(typed),
                    display=entry.name + ("/" if is_dir else ""),
                    display_meta="dir" if is_dir else entry.suffix or "file",
                )
            return

        # --- /command completion ---
        if text.startswith("/"):
            for cmd in COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))


async def start(working_dir: Path):
    ctx = await bootstrap(working_dir)

    print(BANNER)
    console.print(f"[dim]   dir:[/dim]   [bold]{working_dir}[/bold]")
    console.print(f"[dim]   model:[/dim] [bold]{ctx['config'].model}[/bold]")
    console.print(
        f"[dim]   cmds:[/dim]  /cost /clear /new /init /sessions /switch <n> /exit"
    )
    console.print(
        f"[dim]   tip:[/dim]   Ctrl+C during agent run = interrupt, Ctrl+C at prompt = exit"
    )

    provider = ctx["provider"]
    history = ctx["history"]
    session_id = ctx["session_id"]

    msg_count = len(history.messages)
    if msg_count > 0:
        console.print(
            f"[dim]   session:[/dim] [cyan]{session_id[:8]}[/cyan]  [dim]{msg_count} messages loaded[/dim]"
        )
    else:
        console.print(
            f"[dim]   session:[/dim] [cyan]{session_id[:8]}[/cyan]  [dim]new[/dim]"
        )
    print()

    session_in, session_out = 0, 0
    prompt = PromptSession(
        completer=SlarkCompleter(working_dir),
        complete_while_typing=True,
    )

    while True:
        try:
            task = await prompt.prompt_async(">> ")
            task = task.strip()
        except KeyboardInterrupt:
            # Ctrl+C at prompt = exit
            print(GOODBYE)
            break
        except EOFError:
            print(GOODBYE)
            break

        if not task:
            continue

        if task in ("/exit", "/quit"):
            print(GOODBYE)
            break

        # ── /clear ──────────────────────────────────────────────────────
        if task == "/clear":
            if session_id:
                await clear_session_messages(session_id)
            history.clear()
            console.print(
                f"[green]✓ Session {session_id[:8] if session_id else ''} cleared.[/green]"
            )
            continue

        # ── /new ────────────────────────────────────────────────────────
        if task == "/new":
            session_id = await new_session(working_dir)
            history.clear()
            session_in, session_out = 0, 0
            console.print(
                f"[green]✓ New session [cyan]{session_id[:8]}[/cyan] started.[/green]"
            )
            continue

        # ── /cost ───────────────────────────────────────────────────────
        if task == "/cost":
            cost = estimate_cost(session_in, session_out)
            console.print(
                f"[dim]Session:[/dim] {session_in} in / {session_out} out tokens | "
                f"[bold]~${cost:.4f}[/bold]"
            )
            continue

        # ── /init ───────────────────────────────────────────────────────
        if task == "/init":
            from tools.index import build

            result = await build(working_dir)
            console.print(
                f"[green]✓ Indexed {result['files']} files, {result['symbols']} symbols[/green]"
            )
            continue

        # ── /sessions ───────────────────────────────────────────────────
        if task == "/sessions":
            sessions = await list_sessions(str(working_dir))
            if not sessions:
                console.print("[dim]No sessions yet.[/dim]")
                continue
            console.print()
            for i, s in enumerate(sessions):
                marker = (
                    "[bold green]●[/bold green]"
                    if s["id"] == session_id
                    else "[dim]○[/dim]"
                )
                created = s["created_at"][:16].replace("T", " ")
                sid = s["id"][:8]
                count = s["message_count"]
                console.print(
                    f"  {marker} [bold]{i + 1}.[/bold] [cyan]{sid}[/cyan]"
                    f"  [dim]{created}[/dim]  {count} msg"
                )
            console.print()
            continue

        # ── /switch <n|id> ──────────────────────────────────────────────
        if task.startswith("/switch "):
            arg = task.split(" ", 1)[1].strip()
            sessions = await list_sessions(str(working_dir))

            target = None
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(sessions):
                    target = sessions[idx]
            else:
                target = next((s for s in sessions if s["id"].startswith(arg)), None)

            if not target:
                console.print(f"[red]Session not found:[/red] {arg}")
                continue

            msgs = await load_session(target["id"])
            history.clear()
            for m in msgs:
                if m["role"] == "user":
                    history.add_user(m["content"])
                elif m["role"] == "assistant":
                    history.add_assistant(m["content"])

            session_id = target["id"]
            created = target["created_at"][:16].replace("T", " ")

            console.print()
            console.print(
                f"[bold]Session [cyan]{session_id[:8]}[/cyan][/bold]"
                f"  [dim]{created}[/dim]  {len(msgs)} messages"
            )
            console.print("[dim]" + "─" * 60 + "[/dim]")
            _print_session_history(msgs)
            console.print("[dim]" + "─" * 60 + "[/dim]")
            console.print(
                f"[green]✓ Switched. Continuing from message {len(msgs) + 1}.[/green]"
            )
            console.print()
            continue

        # ── main agent call ──────────────────────────────────────────────

        if session_id is None:
            session_id, _ = await get_or_create_session(working_dir)
            console.print(f"[dim]session {session_id[:8]}[/dim]")

        expanded_task, attached = _expand_file_refs(task, working_dir)

        history.add_user(expanded_task)
        await save_message(session_id, "user", task)

        # Interrupt event — Ctrl+C during agent run cancels the task
        interrupt_event = asyncio.Event()

        def _on_sigint():
            if not interrupt_event.is_set():
                console.print("\n[yellow]⚠ Interrupting...[/yellow]")
                interrupt_event.set()

        loop = asyncio.get_event_loop()
        loop.add_signal_handler(__import__("signal").SIGINT, _on_sigint)

        try:
            agent_task = asyncio.create_task(
                ask(provider, history.get(), working_dir, session_id)
            )
            interrupt_task = asyncio.create_task(interrupt_event.wait())

            done, pending = await asyncio.wait(
                [agent_task, interrupt_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for t in pending:
                t.cancel()

            if interrupt_event.is_set():
                console.print("[yellow]Interrupted.[/yellow]")
                # Roll back the user message from in-memory history
                if history.messages and history.messages[-1]["role"] == "user":
                    history.messages.pop()
                print()
                continue

            answer, input_tokens, output_tokens = agent_task.result()

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            if history.messages and history.messages[-1]["role"] == "user":
                history.messages.pop()
            continue
        finally:
            # Restore default Ctrl+C behaviour at prompt
            loop.add_signal_handler(
                __import__("signal").SIGINT,
                lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
            )

        session_in += input_tokens
        session_out += output_tokens
        cost = estimate_cost(input_tokens, output_tokens)

        history.add_assistant(answer)
        await save_message(session_id, "assistant", answer)
        await save_to_dataset(session_id, history.get())

        print()
        _render_answer(answer)
        print()
        console.print(
            f"[dim][{input_tokens} in / {output_tokens} out | ~${cost:.4f}][/dim]"
        )
        print()
