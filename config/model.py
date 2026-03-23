from dataclasses import dataclass


@dataclass
class Config:
    model: str = "deepseek/deepseek-v3.2"
    provider: str = "openrouter"

    orchestrator_model: str = "deepseek/deepseek-r1-0528"
    orchestrator_provider: str = "openrouter"

    openrouter_key: str = ""

    azure_key: str = ""
    azure_endpoint: str = ""
    azure_deployment: str = "DeepSeek-V3.2"
    azure_api_version: str = "2024-12-01-preview"

    prune_threshold: int = 80_000
    large_context: int = 50_000

    price_in: float = 0.27 / 1_000_000
    price_out: float = 0.79 / 1_000_000
