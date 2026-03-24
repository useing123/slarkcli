import asyncio
import signal
from pathlib import Path

from prompt_toolkit import PromptSession
from rich.console import Console

from agents.bootstrap import bootstrap
from agents.solo import ask, estimate_cost
from memory.database import (
    get_or_create_session,
    save_message,
    save_to_dataset,
)
from ui.attachments import expand_file_refs
from ui.banner import BANNER, GOODBYE
from ui.commands import handle_command
from ui.completer import SlarkCompleter
from ui.render import render_markdown, render_session_history

console = Console()


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
    try:
        loop.add_signal_handler(signal.SIGINT, _on_sigint)
    except NotImplementedError:
        pass

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
            return None, True
        return agent_task.result(), False
    finally:
        try:
            loop.add_signal_handler(
                signal.SIGINT,
                lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
            )
        except NotImplementedError:
            pass


async def start(working_dir: Path, problem: str | None = None):
    ctx = await bootstrap(working_dir)

    console.print(BANNER)
    console.print(f"[dim]   dir:[/dim]   [bold]{working_dir}[/bold]")
    console.print(f"[dim]   model:[/dim] [bold]{ctx['config'].model}[/bold]")
    console.print(
        "[dim]   cmds:[/dim]  /cost /clear /new /init /sessions /switch <n> /settings /exit"
    )
    console.print(
        "[dim]   tip:[/dim]   Ctrl+C during agent = interrupt | @file to attach"
    )

    provider = ctx["provider"]
    config = ctx["config"]
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
    prompt_session = PromptSession(
        completer=SlarkCompleter(working_dir),
        complete_while_typing=True,
    )

    if problem:
        expanded_task, _ = expand_file_refs(problem, working_dir)
        history.add_user(expanded_task)
        await save_message(session_id, "user", problem)

        result, interrupted = await _run_with_interrupt(
            ask(provider, history.get(), working_dir, session_id, config),
        )

        if not interrupted:
            answer, input_tokens, output_tokens = result
            history.add_assistant(answer)
            await save_message(session_id, "assistant", answer)

        return

    while True:
        try:
            task = await prompt_session.prompt_async(">> ")
            task = task.strip()
        except KeyboardInterrupt:
            console.print(GOODBYE)
            break
        except EOFError:
            console.print(GOODBYE)
            break

        if not task:
            continue

        if task in ("/exit", "/quit"):
            console.print(GOODBYE)
            break

        result = await handle_command(
            task,
            session_id=session_id,
            working_dir=working_dir,
            history=history,
            config=config,
            provider=provider,
            session_in=session_in,
            session_out=session_out,
        )

        if result:
            action = result["action"]

            if action == "settings":
                if result.get("changed"):
                    config = result["config"]
                    provider = result["provider"]
                    ctx["config"] = config
                    console.print(
                        f"[green]✓ Provider switched to [bold]{config.provider}[/bold] / {config.model}[/green]"
                    )
                continue

            if action == "clear":
                console.print(
                    f"[green]✓ Session {session_id[:8] if session_id else ''} cleared.[/green]"
                )
                continue

            if action == "new":
                session_id = result["session_id"]
                session_in, session_out = 0, 0
                console.print(
                    f"[green]✓ New session [cyan]{session_id[:8]}[/cyan] started.[/green]"
                )
                continue

            if action == "cost":
                cost = result["value"]
                console.print(
                    f"[dim]Session:[/dim] {session_in} in / {session_out} out tokens | [bold]~${cost:.4f}[/bold]"
                )
                continue

            if action == "init":
                value = result["value"]
                console.print(
                    f"[green]✓ Indexed {value['files']} files, {value['symbols']} symbols[/green]"
                )
                continue

            if action == "sessions":
                sessions = result["value"]
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
                    console.print(
                        f"  {marker} [bold]{i + 1}.[/bold] [cyan]{s['id'][:8]}[/cyan]"
                        f"  [dim]{created}[/dim]  {s['message_count']} msg"
                    )
                console.print()
                continue

            if action == "switch":
                session_id = result["session_id"]
                value = result["value"]
                created = value["created_at"][:16].replace("T", " ")

                console.print()
                console.print(
                    f"[bold]Session [cyan]{session_id[:8]}[/cyan][/bold]  [dim]{created}[/dim]  {value['message_count']} messages"
                )
                console.print("[dim]" + "─" * 60 + "[/dim]")
                render_session_history(value["messages"])
                console.print("[dim]" + "─" * 60 + "[/dim]")
                console.print(
                    f"[green]✓ Switched. Continuing from message {value['message_count'] + 1}.[/green]"
                )
                console.print()
                continue

            if action == "error":
                console.print(f"[red]{result['value']}[/red]")
                continue

            continue

        if session_id is None:
            session_id, _ = await get_or_create_session(working_dir)
            console.print(f"[dim]session {session_id[:8]}[/dim]")

        expanded_task, _ = expand_file_refs(task, working_dir)

        history.add_user(expanded_task)
        await save_message(session_id, "user", task)

        def _on_tool(event, name, data):
            if event == "start":
                console.print(f"[dim]→ {name}[/dim]")
            elif event == "end":
                console.print(f"[dim]← {name} done[/dim]")
                if isinstance(data, str) and len(data) > 200:
                    console.print(f"[dim]{data[:200]}...[/dim]")
                else:
                    console.print(f"[dim]{data}[/dim]")

        result, interrupted = await _run_with_interrupt(
            ask(
                provider,
                history.get(),
                working_dir,
                session_id,
                config,
                on_tool=_on_tool,
            ),
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
        cost = estimate_cost(input_tokens, output_tokens, config)

        history.add_assistant(answer)
        await save_message(session_id, "assistant", answer)
        await save_to_dataset(session_id, history.get())

        print()
        render_markdown(answer)
        print()
        console.print(
            f"[dim][{input_tokens} in / {output_tokens} out | ~${cost:.4f}][/dim]"
        )
        print()
