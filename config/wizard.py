from config.model import Config
from config.serializer import save_config


def setup_wizard() -> Config:
    print("⚡ First run — setting up Slark")
    print()

    key = input("OpenRouter API key: ").strip()
    model = input("Model [stealth/ox-alpha]: ").strip() or "stealth/ox-alpha"
    cfg = Config(openrouter_key=key, model=model)

    save_config(cfg)

    print(f"Config saved to config file")

    return cfg
