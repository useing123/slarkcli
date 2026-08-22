from dataclasses import dataclass


@dataclass
class Config:
    model: str = "stealth/ox-alpha"

    openrouter_key: str = ""

    max_iterations: int = 20

    prune_threshold: int = 80_000
    large_context: int = 50_000

    price_in: float = 0.27 / 1_000_000
    price_out: float = 0.79 / 1_000_000
