import json
from pathlib import Path

TRACE_DIR = Path.home() / ".slark" / "traces"


def trace_context(session_id: str, iteration: int, ctx: list[dict]) -> None:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)

    (TRACE_DIR / f"{session_id}_{iteration}.json").write_text(
        json.dumps(ctx, indent=2, ensure_ascii=False)
    )
