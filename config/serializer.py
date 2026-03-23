from pathlib import Path

CONFIG_PATH = Path.home() / ".slark" / "config.toml"


def save_config(config) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    CONFIG_PATH.write_text(
        f"""
[agent]
model    = "{config.model}"
provider = "{config.provider}"

[orchestrator]
model    = "{config.orchestrator_model}"
provider = "{config.orchestrator_provider}"

[keys]
openrouter = "{config.openrouter_key}"

[azure]
api_key     = "{config.azure_key}"
endpoint    = "{config.azure_endpoint}"
deployment  = "{config.azure_deployment}"
api_version = "{config.azure_api_version}"

[context]
prune_threshold = {config.prune_threshold}
large_context   = {config.large_context}

[pricing.openrouter]
price_in  = {0.27 / 1_000_000}
price_out = {0.79 / 1_000_000}

[pricing.azure]
price_in  = {0.27 / 1_000_000}
price_out = {0.79 / 1_000_000}
""".strip()
    )

    CONFIG_PATH.chmod(0o600)
