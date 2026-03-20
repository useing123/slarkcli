# config.py
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path.home() / ".slark" / "config.toml"

DEFAULT_CONFIG = """
[agent]
model = "deepseek/deepseek-v3.2"
provider = "openrouter"

[keys]
openrouter = ""

[context]
prune_threshold = 80000
large_context = 50000

[pricing.openrouter]
price_in = 0.00000027
price_out = 0.00000079
"""


@dataclass
class Config:
    model: str = "deepseek/deepseek-v3.2"
    provider: str = "openrouter"
    openrouter_key: str = ""
    prune_threshold: int = 80_000
    large_context: int = 50_000
    price_in: float = 0.27 / 1_000_000
    price_out: float = 0.79 / 1_000_000

    @classmethod
    def load(cls) -> "Config":
        # fallback to env for backwards compat
        env_key = os.getenv("OPENROUTER_API_KEY", "")

        if not CONFIG_PATH.exists():
            return cls(openrouter_key=env_key)

        with open(CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)

        agent = data.get("agent", {})
        keys = data.get("keys", {})
        ctx = data.get("context", {})
        pricing = data.get("pricing", {}).get("openrouter", {})

        return cls(
            model=agent.get("model", "deepseek/deepseek-v3.2"),
            provider=agent.get("provider", "openrouter"),
            openrouter_key=keys.get("openrouter", "") or env_key,
            prune_threshold=ctx.get("prune_threshold", 80_000),
            large_context=ctx.get("large_context", 50_000),
            price_in=pricing.get("price_in", 0.27 / 1_000_000),
            price_out=pricing.get("price_out", 0.79 / 1_000_000),
        )

    def save(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            f"""
[agent]
model = "{self.model}"
provider = "{self.provider}"

[keys]
openrouter = "{self.openrouter_key}"

[context]
prune_threshold = {self.prune_threshold}
large_context = {self.large_context}

[pricing.openrouter]
price_in = {self.price_in}
price_out = {self.price_out}
""".strip()
        )
        CONFIG_PATH.chmod(0o600)

    @classmethod
    def setup_wizard(cls) -> "Config":
        print("⚡ First run — setting up Slark")
        print()
        key = input("OpenRouter API key: ").strip()
        model = (
            input("Model [deepseek/deepseek-v3.2]: ").strip()
            or "deepseek/deepseek-v3.2"
        )
        cfg = cls(openrouter_key=key, model=model)
        cfg.save()
        print(f"Config saved to {CONFIG_PATH}")
        return cfg
