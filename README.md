# Slark
> Open source AI coding agent. Terminal-first, built for developers who want control.

## Why Slark?

Most coding agents have the same problems:
- They read your `.env` files and secrets
- No real task tracking — everything is a black box
- You don't own your data and can't fine-tune on it
- Linear execution with no orchestration

Slark is an attempt to do this differently.

## Status

This is a **v0.0.1 personal build** — I'm building this for myself and open sourcing it as I go. If you want to try it, contribute ideas, or just follow along — welcome.

> ⚠️ Only OpenRouter is supported as a provider right now.

## Setup

```bash
git clone https://github.com/useing123/slarkcli
cd slarkcli

uv venv
uv pip install -r requirements.txt

# First run will prompt you for your API key and model
uv run python main.py --dir /path/to/your/project
```

Config is saved to `~/.slark/config.toml` — never committed to the repo.

## Run

```bash
uv run python main.py --dir /path/to/your/project
```

With session tracing (saves every LLM request to `~/.slark/traces/`):

```bash
SLARK_TRACE=1 uv run python main.py --dir /path/to/your/project
```

## Chat commands

```
>> /cost          — token usage and cost for this session
>> /sessions      — list all sessions for this project
>> /switch <n>    — switch to session by number or ID prefix
>> /new           — start a new session (current is archived)
>> /clear         — wipe current session messages from memory and DB
>> /init          — re-index the project
>> /exit          — quit
```

**File context:** type `@filename` in any message to attach a file:

```
>> look at @src/components/Button.tsx and refactor it
>> compare @api/routes.py @api/models.py
```

Tab completion works for both `@filename` and `/commands`.

**Interrupt:** `Ctrl+C` during agent run stops it and returns to prompt. `Ctrl+C` at prompt exits.

## What works right now

### 🔒 Security first
- Never reads `.env`, `.git/`, `~/.ssh/` or any secrets — hardcoded, not prompt-based
- Dangerous commands require explicit user confirmation
- `move_to_garbage` instead of `rm` — deleted files are always recoverable from `~/.slark/garbage/`

### 🗂️ Sessions
- Full session history saved to SQLite at `~/.slark/slark.db`
- Switch between sessions and continue from where you left off
- Sessions are scoped per project directory — different projects don't mix

### 🗂️ Task board
- Agent tracks its own progress using structured tasks
- Every subtask is created, updated, and verified before moving on
- Stored in SQLite — query your agent's work history anytime

### 🧠 Context management
- Automatic context pruning when token budget gets large
- AST-based project index — `search_symbol`, `get_file_symbols`, `index_summary`
- Session traces saved locally at `~/.slark/traces/`

### 🛠️ Tool suite
- `read_file`, `read_lines`, `tree`, `outline` — smart file reading with 150-line truncation
- `write_file`, `str_replace`, `create_dir`, `move_to_garbage` — safe editing
- `grep`, `find_definition` — code search across Python, TS, JS, Go, Rust
- `run_command`, `run_background`, `check_port`, `kill_background` — process control
- `create_task`, `update_task`, `list_tasks` — task management
- `search_symbol`, `get_file_symbols`, `index_summary` — AST index

### 📊 Dataset collection
- All conversations saved to SQLite for fine-tuning
- Export anytime

## Stack

- **Python + asyncio** — core
- **SQLite + aiosqlite** — storage, sessions, task board, dataset
- **OpenAI SDK → OpenRouter** — LLM calls
- **prompt_toolkit** — tab completion for `@files` and `/commands`
- **rich** — markdown rendering in terminal
- **pathspec** — `.gitignore`-aware file traversal

## Config

Auto-generated at `~/.slark/config.toml` on first run:

```toml
[agent]
model = "deepseek/deepseek-v3.2"
provider = "openrouter"

[keys]
openrouter = "sk-..."

[context]
prune_threshold = 80000
large_context = 50000

[pricing.openrouter]
price_in = 0.00000027
price_out = 0.00000079
```

## Roadmap

**Next up:**
- [ ] Streaming output — see the agent think in real time
- [ ] Command allowlist/blocklist via `config.toml`
- [ ] Gemini provider
- [ ] Web search + fetch URL tools

**Orchestration:**
- [ ] Orchestrator agent — decomposes tasks, never writes code itself
- [ ] Architect/Librarian agent — answers questions about the codebase via Project Index
- [ ] Coder agent — focused purely on writing and editing code
- [ ] Reviewer agent — verifies the coder's output

**Swarm mode:**
- [ ] Parallel workers — multiple agents tackle the same problem with different approaches
- [ ] Orchestrator picks the winner

**Memory:**
- [ ] Cross-session knowledge base — agent remembers your project
- [ ] Vector memory via sqlite-vec
- [ ] Session summarizer

**UI:**
- [ ] TUI via Textual
- [ ] Web dashboard — real-time swarm visualization

## Philosophy

- Your data belongs to you
- The agent only does what you explicitly allow
- No hidden magic — all code is readable

## Contributing

PRs and ideas welcome. Still early — things will break and change.

## License

MIT
