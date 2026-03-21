"""
Interactive /settings menu — no need to edit config.toml manually.
Changes apply immediately without restart.
"""

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from rich.console import Console
from rich.table import Table

from config import Config

console = Console()

OPENROUTER_MODELS = [
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

ORCHESTRATOR_MODELS = [
    "deepseek/deepseek-r1-0528",
    "deepseek/deepseek-r1",
    "deepseek/deepseek-v3.2",
    "anthropic/claude-opus-4-5",
    "openai/o3",
    "google/gemini-2.5-pro",
    "kimi-k2-5",
    "grok-4-1-fast-reasoning",
]

AZURE_DEPLOYMENTS = [
    "DeepSeek-V3.2",
    "deepseek-r1",
    "kimi-k2-5",
    "grok-4-1-fast-reasoning",
]


def _show_current(config: Config):
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("key", style="dim")
    table.add_column("value", style="bold")

    table.add_row("provider", config.provider)
    table.add_row("model", config.model)
    table.add_row("orch provider", config.orchestrator_provider)
    table.add_row("orch model", config.orchestrator_model)

    if config.provider == "openrouter":
        k = config.openrouter_key
        display = (
            ("sk-..." + k[-4:])
            if len(k) > 8
            else ("set" if k else "[red]not set[/red]")
        )
        table.add_row("openrouter key", display)
    elif config.provider == "azure":
        k = config.azure_key
        display = (
            ("***" + k[-4:]) if len(k) > 8 else ("set" if k else "[red]not set[/red]")
        )
        table.add_row("azure key", display)
        table.add_row("azure endpoint", config.azure_endpoint or "[red]not set[/red]")
        table.add_row("azure deployment", config.azure_deployment)
        table.add_row("azure api version", config.azure_api_version)

    table.add_row("prune threshold", str(config.prune_threshold))

    console.print()
    console.print("[bold]Current settings[/bold]")
    console.print(table)
    console.print()


async def _ask(
    session: PromptSession, question: str, default: str = "", completer=None
) -> str:
    """Async prompt with default value shown in brackets."""
    display = f"{question} [{default}]: " if default else f"{question}: "
    try:
        val = await session.prompt_async(display, completer=completer)
        return val.strip() or default
    except (KeyboardInterrupt, EOFError):
        return default


async def run_settings(config: Config) -> tuple[Config, bool]:
    """Show settings menu, return (updated_config, was_changed)."""
    _show_current(config)
    console.print("[dim]Leave blank to keep current value. Ctrl+C to cancel.[/dim]")
    console.print()

    session = PromptSession()
    changed = False

    # Provider
    new_provider = await _ask(
        session,
        "provider (openrouter / azure)",
        config.provider,
        WordCompleter(["openrouter", "azure"], sentence=True),
    )
    if new_provider != config.provider:
        config.provider = new_provider
        changed = True

    # Orchestrator
    new_orch_provider = await _ask(
        session,
        "orchestrator provider (openrouter / azure)",
        config.orchestrator_provider,
        WordCompleter(["openrouter", "azure"], sentence=True),
    )
    if new_orch_provider != config.orchestrator_provider:
        config.orchestrator_provider = new_orch_provider
        changed = True

    new_orch_model = await _ask(
        session,
        "orchestrator model",
        config.orchestrator_model,
        WordCompleter(ORCHESTRATOR_MODELS, sentence=True),
    )
    if new_orch_model != config.orchestrator_model:
        config.orchestrator_model = new_orch_model
        changed = True

    # Worker provider-specific
    if config.provider == "openrouter":
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
            session, "openrouter api key", "********" if config.openrouter_key else ""
        )
        if new_key and new_key != "********":
            config.openrouter_key = new_key
            changed = True

    elif config.provider == "azure":
        new_deploy = await _ask(
            session,
            "azure deployment",
            config.azure_deployment,
            WordCompleter(AZURE_DEPLOYMENTS, sentence=True),
        )
        if new_deploy != config.azure_deployment:
            config.azure_deployment = new_deploy
            config.model = new_deploy
            changed = True

        new_endpoint = await _ask(session, "azure endpoint", config.azure_endpoint)
        if new_endpoint != config.azure_endpoint:
            config.azure_endpoint = new_endpoint
            changed = True

        new_api_version = await _ask(
            session, "azure api version", config.azure_api_version
        )
        if new_api_version != config.azure_api_version:
            config.azure_api_version = new_api_version
            changed = True

        console.print("[dim]  paste full key or leave blank to keep[/dim]")
        new_key = await _ask(
            session, "azure api key", "********" if config.azure_key else ""
        )
        if new_key and new_key != "********":
            config.azure_key = new_key
            changed = True

    # Context
    new_prune = await _ask(
        session, "prune threshold (tokens)", str(config.prune_threshold)
    )
    try:
        val = int(new_prune)
        if val != config.prune_threshold:
            config.prune_threshold = val
            changed = True
    except ValueError:
        pass

    if changed:
        config.save()
        console.print()
        console.print("[green]✓ Settings saved to ~/.slark/config.toml[/green]")
    else:
        console.print()
        console.print("[dim]No changes.[/dim]")

    console.print()
    return config, changed
