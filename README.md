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

This is a **v0.0.1 personal build** — I'm building this for myself and open sourcing it as I go. If you want to try it, contribute ideas, or just follow along - welcome.

> ⚠️ Only OpenRouter is supported as a provider right now.

## Setup

```bash
git clone https://github.com/useing123/slark
cd slark

# create venv and install deps
uv venv
uv pip install -r requirements.txt

# add your API key
cp .env.example .env
# set OPENROUTER_API_KEY in .env
```

## Run

```bash
uv run python main.py --dir /path/to/your/project
```

With session tracing (saves every LLM request to `~/.slark/traces/`):

```bash
SLARK_TRACE=1 uv run python main.py --dir /path/to/your/project
```

## What works right now (v0.0.1)

### 🔒 Security first
- Never reads `.env`, `.git/`, `~/.ssh/` or any secrets — hardcoded, not prompt-based
- Dangerous commands require explicit user confirmation
- `move_to_garbage` instead of `rm` — deleted files are always recoverable from `~/.slark/garbage/`

### 🗂️ Task board
- Agent tracks its own progress using structured tasks
- Every subtask is created, updated, and verified before moving on
- Stored in SQLite — query your agent's work history anytime

### 🧠 Context management
- Automatic context pruning when token budget gets large
- Structured JSON responses from all tools — consistent format for fine-tuning
- Session traces saved locally at `~/.slark/traces/`

### 🛠️ Tool suite
- `read_file`, `read_lines`, `tree`, `outline` — smart file reading with truncation at 150 lines
- `write_file`, `str_replace`, `create_dir`, `move_to_garbage` — safe editing
- `grep`, `find_definition` — code search across Python, TS, JS, Go, Rust
- `run_command`, `run_background`, `check_port`, `kill_background` — process control
- `create_task`, `update_task`, `list_tasks` — task management

### 📊 Dataset collection
- All tool calls and responses saved to SQLite
- Export anytime for fine-tuning

## Commands

```bash
>> /cost       # show token usage and cost for this session
>> /clear      # start a new session
>> /exit       # quit
```

## Stack

- **Python + asyncio** — core
- **SQLite + aiosqlite** — storage, task board, dataset
- **OpenAI SDK → OpenRouter** — LLM calls (only OpenRouter supported for now)
- **pathspec** — .gitignore-aware file traversal

## Roadmap

**Next up:**
- [ ] Streaming output — see the agent think in real time
- [ ] Graceful error handling in tool execution
- [ ] Project Index — deterministic AST-based codebase map, zero tokens wasted
- [ ] Web search + fetch URL tools — agent reads actual documentation
- [ ] SWE-bench evaluation

**Orchestration:**
- [ ] Orchestrator agent — decomposes tasks, never writes code itself
- [ ] Architect/Librarian agent — answers questions about the codebase
- [ ] Coder agent — focused purely on writing and editing code
- [ ] Reviewer agent — verifies the coder's output

**Swarm mode:**
- [ ] Parallel workers — multiple agents tackle the same problem with different approaches
- [ ] Debate mode — agents verify each other's solutions
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
- No hidden magic - all code is readable

## Contributing

PRs and ideas welcome. Still early — things will break and change.

## License

MIT
