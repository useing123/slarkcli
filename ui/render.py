from rich.console import Console
from rich.markdown import Markdown

console = Console()


def render_markdown(text: str) -> None:
    if text and text.strip():
        console.print(Markdown(text))


def render_session_history(msgs: list[dict]) -> None:
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
            if content.strip():
                console.print(Markdown(content))
        console.print()
