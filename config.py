import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path.home() / ".slark" / "config.toml"


@dataclass
class Config:
    # Agent (worker)
    model: str = "deepseek/deepseek-v3.2"
    provider: str = "openrouter"

    # Orchestrator
    orchestrator_model: str = "deepseek/deepseek-r1-0528"
    orchestrator_provider: str = "openrouter"

    # OpenRouter
    openrouter_key: str = ""

    # Azure
    azure_key: str = ""
    azure_endpoint: str = ""
    azure_deployment: str = "DeepSeek-V3.2"
    azure_api_version: str = "2024-12-01-preview"

    # Context
    prune_threshold: int = 80_000
    large_context: int = 50_000

    # Pricing
    price_in: float = 0.27 / 1_000_000
    price_out: float = 0.79 / 1_000_000

    @classmethod
    def load(cls) -> "Config":
        env_or_key = os.getenv("OPENROUTER_API_KEY", "")

        if not CONFIG_PATH.exists():
            return cls(openrouter_key=env_or_key)

        with open(CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)

        agent = data.get("agent", {})
        orch = data.get("orchestrator", {})
        keys = data.get("keys", {})
        azure = data.get("azure", {})
        ctx = data.get("context", {})
        pricing = data.get("pricing", {}).get(agent.get("provider", "openrouter"), {})

        return cls(
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

    def save(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            f"""
[agent]
model    = "{self.model}"
provider = "{self.provider}"

[orchestrator]
model    = "{self.orchestrator_model}"
provider = "{self.orchestrator_provider}"

[keys]
openrouter = "{self.openrouter_key}"

[azure]
api_key     = "{self.azure_key}"
endpoint    = "{self.azure_endpoint}"
deployment  = "{self.azure_deployment}"
api_version = "{self.azure_api_version}"

[context]
prune_threshold = {self.prune_threshold}
large_context   = {self.large_context}

[pricing.openrouter]
price_in  = {0.27 / 1_000_000}
price_out = {0.79 / 1_000_000}

[pricing.azure]
price_in  = {0.27 / 1_000_000}
price_out = {0.79 / 1_000_000}
""".strip()
        )
        CONFIG_PATH.chmod(0o600)

    @classmethod
    def setup_wizard(cls) -> "Config":
        print("⚡ First run — setting up Slark")
        print()
        print("Provider:")
        print("  1. OpenRouter")
        print("  2. Azure")
        choice = input("Choose [1]: ").strip() or "1"

        if choice == "2":
            azure_key = input("Azure API key: ").strip()
            azure_endpoint = input("Azure endpoint (https://...): ").strip()
            azure_deployment = (
                input("Deployment name [DeepSeek-V3.2]: ").strip() or "DeepSeek-V3.2"
            )
            cfg = cls(
                provider="azure",
                model=azure_deployment,
                azure_key=azure_key,
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
            )
        else:
            key = input("OpenRouter API key: ").strip()
            model = (
                input("Model [deepseek/deepseek-v3.2]: ").strip()
                or "deepseek/deepseek-v3.2"
            )
            cfg = cls(provider="openrouter", openrouter_key=key, model=model)

        cfg.save()
        print(f"Config saved to {CONFIG_PATH}")
        return cfg
