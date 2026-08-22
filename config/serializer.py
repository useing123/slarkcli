from pathlib import Path

CONFIG_PATH = Path.home() / ".slark" / "config.toml"


def save_config(config) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    CONFIG_PATH.write_text(
        f"""
[agent]
model          = "{config.model}"
max_iterations = {config.max_iterations}

[keys]
openrouter = "{config.openrouter_key}"

[context]
prune_threshold = {config.prune_threshold}
large_context   = {config.large_context}

[pricing.openrouter]
price_in  = {config.price_in}
price_out = {config.price_out}
""".strip()
    )

    CONFIG_PATH.chmod(0o600)
