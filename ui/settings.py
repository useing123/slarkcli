from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from rich.console import Console
from rich.table import Table

from config.model import Config
from config.serializer import save_config

console = Console()

OPENROUTER_MODELS = [
    "stealth/ox-alpha",
    "deepseek/deepseek-v3.2",
    "deepseek/deepseek-chat",
    "deepseek/deepseek-r1-0528",
    "deepseek/deepseek-r1",
    "anthropic/claude-sonnet-4-5",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "google/gemini-2.5-pro",
    "qwen/qwen-2.5-coder-32b-instruct",
]


def _show_current(config: Config):
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("key", style="dim")
    table.add_column("value", style="bold")

    table.add_row("model", config.model)

    k = config.openrouter_key
    display = (
        ("sk-..." + k[-4:]) if len(k) > 8 else ("set" if k else "[red]not set[/red]")
    )
    table.add_row("openrouter key", display)

    table.add_row("max iterations", str(config.max_iterations))
    table.add_row("prune threshold", str(config.prune_threshold))

    console.print()
    console.print("[bold]Current settings[/bold]")
    console.print(table)
    console.print()


async def _ask(
    session: PromptSession,
    question: str,
    default: str = "",
    completer=None,
) -> str:
    display = f"{question} [{default}]: " if default else f"{question}: "
    try:
        val = await session.prompt_async(display, completer=completer)
        return val.strip() or default
    except (KeyboardInterrupt, EOFError):
        return default


async def run_settings(config: Config) -> tuple[Config, bool]:
    _show_current(config)

    console.print("[dim]Leave blank to keep current value. Ctrl+C to cancel.[/dim]")
    console.print()

    session = PromptSession()
    changed = False

    new_model = await _ask(
        session,
        "model",
        config.model,
        WordCompleter(OPENROUTER_MODELS, sentence=True),
    )
    if new_model != config.model:
        config.model = new_model
        changed = True

    console.print("[dim]  paste full key or leave blank to keep[/dim]")
    new_key = await _ask(
        session,
        "openrouter api key",
        "********" if config.openrouter_key else "",
    )
    if new_key and new_key != "********":
        config.openrouter_key = new_key
        changed = True

    new_max_iter = await _ask(
        session,
        "max iterations",
        str(config.max_iterations),
    )
    try:
        val = int(new_max_iter)
        if val != config.max_iterations:
            config.max_iterations = val
            changed = True
    except ValueError:
        pass

    # Context
    new_prune = await _ask(
        session,
        "prune threshold (tokens)",
        str(config.prune_threshold),
    )

    try:
        val = int(new_prune)
        if val != config.prune_threshold:
            config.prune_threshold = val
            changed = True
    except ValueError:
        pass

    if changed:
        save_config(config)
        console.print()
        console.print("[green]✓ Settings saved to ~/.slark/config.toml[/green]")
    else:
        console.print()
        console.print("[dim]No changes.[/dim]")

    console.print()
    return config, changed
