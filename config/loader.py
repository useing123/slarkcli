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
    orch = data.get("orchestrator", {})
    keys = data.get("keys", {})
    azure = data.get("azure", {})
    ctx = data.get("context", {})
    pricing = data.get("pricing", {}).get(agent.get("provider", "openrouter"), {})

    return Config(
        model=agent.get("model", "deepseek/deepseek-v3.2"),
        provider=agent.get("provider", "openrouter"),
        orchestrator_model=orch.get("model", "deepseek/deepseek-r1-0528"),
        orchestrator_provider=orch.get("provider", "openrouter"),
        openrouter_key=keys.get("openrouter", "") or env_or_key,
        azure_key=azure.get("api_key", "") or os.getenv("AZURE_OPENAI_API_KEY", ""),
        azure_endpoint=azure.get("endpoint", "")
        or os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        azure_deployment=azure.get("deployment", "DeepSeek-V3.2"),
        azure_api_version=azure.get("api_version", "2024-12-01-preview"),
        prune_threshold=ctx.get("prune_threshold", 80_000),
        large_context=ctx.get("large_context", 50_000),
        price_in=pricing.get("price_in", 0.27 / 1_000_000),
        price_out=pricing.get("price_out", 0.79 / 1_000_000),
    )
