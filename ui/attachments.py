import re
from pathlib import Path

from rich.console import Console

console = Console()
_ATTACHMENT_RE = re.compile(r"@([\w./\-]+)")


def expand_file_refs(task: str, working_dir: Path) -> tuple[str, list[str]]:
    """Find @filename refs, read files, inject contents into the message."""
    refs = _ATTACHMENT_RE.findall(task)
    if not refs:
        return task, []

    root = working_dir.resolve()
    attached: list[str] = []
    blocks: list[str] = []

    for ref in refs:
        path = (root / ref).resolve()

        try:
            path.relative_to(root)
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

        rel = path.relative_to(root)
        blocks.append(f'<file path="{rel}">\n{content}\n</file>')
        attached.append(str(rel))
        console.print(f"[dim]  📎 {rel} ({len(content.splitlines())} lines)[/dim]")

    if not blocks:
        return task, []

    clean_task = _ATTACHMENT_RE.sub("", task).strip()
    return clean_task + "\n\n" + "\n\n".join(blocks), attached
