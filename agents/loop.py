import asyncio
import re
import signal
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
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
    "/swarm",
    "/solo",
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
    return clean_task + "\n\n" + "\n\n".join(blocks), attached


class SlarkCompleter(Completer):
    """Autocomplete: @filename and /commands."""

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir.resolve()

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        at_match = re.search(r"@([\w./\-]*)$", text)
        if at_match:
            typed = at_match.group(1)
            if "/" in typed:
                parts = typed.rsplit("/", 1)
                search_dir = self.working_dir / parts[0]
                name_prefix = parts[1]
            else:
                search_dir = self.working_dir
                name_prefix = typed

            if not search_dir.is_dir():
                return
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
                yield Completion(
                    str(rel) + ("/" if is_dir else ""),
                    start_position=-len(typed),
                    display=entry.name + ("/" if is_dir else ""),
                    display_meta="dir" if is_dir else entry.suffix or "file",
                )
            return

        if text.startswith("/"):
            for cmd in COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))


async def _run_with_interrupt(coro, label: str = ""):
    """Run a coroutine, allow Ctrl+C to cancel it without exiting the app."""
    interrupt_event = asyncio.Event()

    def _on_sigint():
        if not interrupt_event.is_set():
            console.print(
                f"\n[yellow]⚠ Interrupting{' ' + label if label else ''}...[/yellow]"
            )
            interrupt_event.set()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, _on_sigint)

    try:
        agent_task = asyncio.create_task(coro)
        interrupt_task = asyncio.create_task(interrupt_event.wait())
        done, pending = await asyncio.wait(
            [agent_task, interrupt_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        if interrupt_event.is_set():
            return None, True  # (result, was_interrupted)
        return agent_task.result(), False
    finally:
        loop.add_signal_handler(
            signal.SIGINT,
            lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
        )


async def start(working_dir: Path):
    ctx = await bootstrap(working_dir)

    print(BANNER)
    console.print(f"[dim]   dir:[/dim]   [bold]{working_dir}[/bold]")
    console.print(f"[dim]   model:[/dim] [bold]{ctx['config'].model}[/bold]")
    console.print(
        f"[dim]   cmds:[/dim]  /cost /clear /new /init /sessions /switch <n> /swarm /solo /settings /exit"
    )
    console.print(
        f"[dim]   tip:[/dim]   Ctrl+C during agent = interrupt  |  /swarm to enter orchestrator mode"
    )

    provider = ctx["provider"]
    history = ctx["history"]
    session_id = ctx["session_id"]

    # Orchestrator mode state — separate session and history from solo
    orch_mode = False
    orch_session_id: str | None = None
    orch_history = History()

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
    prompt_session = PromptSession(
        completer=SlarkCompleter(working_dir),
        complete_while_typing=True,
    )

    while True:
        # Prompt prefix shows current mode
        prefix = "[orch]>> " if orch_mode else ">> "

        try:
            task = await prompt_session.prompt_async(prefix)
            task = task.strip()
        except KeyboardInterrupt:
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

        # ── /settings ───────────────────────────────────────────────────
        if task == "/settings":
            from ui.settings import run_settings

            new_config, changed = await run_settings(ctx["config"])
            if changed:
                ctx["config"] = new_config
                # Rebuild provider with new settings
                from agents.bootstrap import get_provider

                try:
                    provider = get_provider(new_config)
                    console.print(
                        f"[green]✓ Provider switched to [bold]{new_config.provider}[/bold] / {new_config.model}[/green]"
                    )
                except Exception as e:
                    console.print(f"[red]Provider error: {e}[/red]")
            continue

        # ── /clear ──────────────────────────────────────────────────────
        if task == "/clear":
            if orch_mode:
                if orch_session_id:
                    await clear_session_messages(orch_session_id)
                orch_history.clear()
                console.print("[green]✓ Orchestrator session cleared.[/green]")
            else:
                if session_id:
                    await clear_session_messages(session_id)
                history.clear()
                console.print(
                    f"[green]✓ Session {session_id[:8] if session_id else ''} cleared.[/green]"
                )
            continue

        # ── /new ────────────────────────────────────────────────────────
        if task == "/new":
            if orch_mode:
                orch_session_id = await new_session(working_dir)
                orch_history.clear()
                console.print(
                    f"[green]✓ New orchestrator session [cyan]{orch_session_id[:8]}[/cyan].[/green]"
                )
            else:
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
                f"[dim]Session:[/dim] {session_in} in / {session_out} out tokens | [bold]~${cost:.4f}[/bold]"
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
            active_id = orch_session_id if orch_mode else session_id
            for i, s in enumerate(sessions):
                marker = (
                    "[bold green]●[/bold green]"
                    if s["id"] == active_id
                    else "[dim]○[/dim]"
                )
                created = s["created_at"][:16].replace("T", " ")
                console.print(
                    f"  {marker} [bold]{i + 1}.[/bold] [cyan]{s['id'][:8]}[/cyan]"
                    f"  [dim]{created}[/dim]  {s['message_count']} msg"
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

            if orch_mode:
                orch_history.clear()
                for m in msgs:
                    if m["role"] == "user":
                        orch_history.add_user(m["content"])
                    elif m["role"] == "assistant":
                        orch_history.add_assistant(m["content"])
                orch_session_id = target["id"]
            else:
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
                f"[bold]Session [cyan]{target['id'][:8]}[/cyan][/bold]"
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

        # ── /swarm — enter orchestrator mode (or one-shot with arg) ─────
        if task == "/swarm" or task.startswith("/swarm "):
            arg = task[6:].strip()  # empty = enter mode, non-empty = one-shot

            if not arg and not orch_mode:
                # Enter orchestrator mode
                orch_mode = True
                if orch_session_id is None:
                    orch_session_id = await new_session(working_dir)
                console.print(
                    f"[bold magenta]🎯 Orchestrator mode[/bold magenta]  "
                    f"[dim]session {orch_session_id[:8]}[/dim]  "
                    f"[dim]type /solo to switch back[/dim]"
                )
                continue

            if not arg and orch_mode:
                console.print(
                    "[dim]Already in orchestrator mode. Type /solo to exit.[/dim]"
                )
                continue

            # One-shot /swarm <task> — run without switching mode
            swarm_task = arg
            target_session = orch_session_id or session_id
            if orch_session_id is None:
                orch_session_id = await new_session(working_dir)
                target_session = orch_session_id

            from agents.orchestrator import orchestrate

            await save_message(target_session, "user", swarm_task)

            result, interrupted = await _run_with_interrupt(
                orchestrate(swarm_task, provider, working_dir, target_session),
                label="orchestrator",
            )

            if interrupted:
                console.print("[yellow]Orchestrator interrupted.[/yellow]")
                continue

            answer, input_tokens, output_tokens = result
            session_in += input_tokens
            session_out += output_tokens
            cost = estimate_cost(input_tokens, output_tokens)
            orch_history.add_assistant(answer)
            print()
            console.print(
                f"[dim][orchestrator | {input_tokens} in / {output_tokens} out | ~${cost:.4f}][/dim]"
            )
            print()
            continue

        # ── /solo — exit orchestrator mode ──────────────────────────────
        if task == "/solo":
            if not orch_mode:
                console.print("[dim]Already in solo mode.[/dim]")
            else:
                orch_mode = False
                console.print(
                    f"[green]✓ Solo mode[/green]  [dim]session {session_id[:8] if session_id else 'new'}[/dim]"
                )
            continue

        # ── orchestrator mode — persistent conversation ──────────────────
        if orch_mode:
            if orch_session_id is None:
                orch_session_id = await new_session(working_dir)

            expanded_task, _ = _expand_file_refs(task, working_dir)
            orch_history.add_user(expanded_task)
            await save_message(orch_session_id, "user", task)

            from agents.orchestrator import orchestrate_turn

            result, interrupted = await _run_with_interrupt(
                orchestrate_turn(
                    orch_history.get(),
                    provider,
                    working_dir,
                    orch_session_id,
                ),
                label="orchestrator",
            )

            if interrupted:
                if (
                    orch_history.messages
                    and orch_history.messages[-1]["role"] == "user"
                ):
                    orch_history.messages.pop()
                console.print("[yellow]Interrupted.[/yellow]")
                continue

            answer, input_tokens, output_tokens = result
            session_in += input_tokens
            session_out += output_tokens
            cost = estimate_cost(input_tokens, output_tokens)

            orch_history.add_assistant(answer)
            await save_message(orch_session_id, "assistant", answer)

            print()
            console.print(
                f"[dim][orch | {input_tokens} in / {output_tokens} out | ~${cost:.4f}][/dim]"
            )
            print()
            continue

        # ── solo agent call ──────────────────────────────────────────────
        if session_id is None:
            session_id, _ = await get_or_create_session(working_dir)
            console.print(f"[dim]session {session_id[:8]}[/dim]")

        expanded_task, _ = _expand_file_refs(task, working_dir)
        history.add_user(expanded_task)
        await save_message(session_id, "user", task)

        result, interrupted = await _run_with_interrupt(
            ask(provider, history.get(), working_dir, session_id),
        )

        if interrupted:
            if history.messages and history.messages[-1]["role"] == "user":
                history.messages.pop()
            console.print("[yellow]Interrupted.[/yellow]")
            print()
            continue

        try:
            answer, input_tokens, output_tokens = result
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            if history.messages and history.messages[-1]["role"] == "user":
                history.messages.pop()
            continue

        session_in += input_tokens
        session_out += output_tokens
        cost = estimate_cost(input_tokens, output_tokens)

        history.add_assistant(answer)
        await save_message(session_id, "assistant", answer)
        await save_to_dataset(session_id, history.get())

        print()
        console.print(
            f"[dim][{input_tokens} in / {output_tokens} out | ~${cost:.4f}][/dim]"
        )
        print()
