import os
import tomllib
from pathlib import Path

from config.model import Config

CONFIG_PATH = Path.home() / ".slark" / "config.toml"


def load_config() -> Config:
    env_or_key = os.getenv("OPENROUTER_API_KEY", "")

    if not CONFIG_PATH.exists():
        return Config(openrouter_key=env_or_key)

    with open(CONFIG_PATH, "rb") as f:
        data = tomllib.load(f)

    agent = data.get("agent", {})
    keys = data.get("keys", {})
    ctx = data.get("context", {})
    pricing = data.get("pricing", {}).get("openrouter", {})

    return Config(
        model=agent.get("model", "stealth/ox-alpha"),
        openrouter_key=keys.get("openrouter", "") or env_or_key,
        max_iterations=agent.get("max_iterations", 20),
        prune_threshold=ctx.get("prune_threshold", 80_000),
        large_context=ctx.get("large_context", 50_000),
        price_in=pricing.get("price_in", 0.27 / 1_000_000),
        price_out=pricing.get("price_out", 0.79 / 1_000_000),
    )
