from config.model import Config
from config.serializer import save_config


def setup_wizard() -> Config:
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
        cfg = Config(
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
        cfg = Config(provider="openrouter", openrouter_key=key, model=model)

    save_config(cfg)

    print(f"Config saved to config file")

    return cfg
