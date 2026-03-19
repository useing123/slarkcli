import os
from pathlib import Path

from dotenv import load_dotenv

from agents.solo import ask, estimate_cost
from memory.database import (
    close_abandoned_tasks,
    init,
    new_session,
    save_message,
    save_to_dataset,
)
from memory.history import History
from providers.openrouter import OpenRouterProvider
from tools.index import build, init_index

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL = "deepseek/deepseek-v3.2"


async def start(working_dir: Path):
    if not API_KEY:
        print("set OPENROUTER_API_KEY")
        return

    await init()
    await init_index()
    print("  🗺 indexing project...")
    result = await build(working_dir)
    print(f"  ✓ {result['files']} files, {result['symbols']} symbols indexed")
    await close_abandoned_tasks(str(working_dir))
    session_id = await new_session(working_dir)
    provider = OpenRouterProvider(api_key=API_KEY, model=MODEL)
    history = History()

    session_in, session_out = 0, 0

    print("⚡ Slark")
    print(f"   dir: {working_dir}")
    print("/cost /clear")
    print()

    while True:
        try:
            task = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not task:
            continue

        if task in ("/exit", "/quit"):
            break

        if task == "/clear":
            history.clear()
            session_id = await new_session(working_dir)
            print("History cleared.")
            continue

        if task == "/cost":
            cost = estimate_cost(session_in, session_out)
            print(f"Session: {session_in} in / {session_out} out tokens | ~${cost:.4f}")
            continue

        if task == "/init":
            result = await build(working_dir)
            print(f"Indexed {result['files']} files, {result['symbols']} symbols")
            continue

        history.add_user(task)
        await save_message(session_id, "user", task)

        answer, input_tokens, output_tokens = await ask(
            provider,
            history.get(),
            working_dir,
            session_id,
        )

        session_in += input_tokens
        session_out += output_tokens
        cost = estimate_cost(input_tokens, output_tokens)

        history.add_assistant(answer)
        await save_message(session_id, "assistant", answer)
        await save_to_dataset(session_id, history.get())

        print()
        print(answer)
        print()
        print(f"[{input_tokens} in / {output_tokens} out | ~${cost:.4f}]")
        print()
