from dataclasses import dataclass, field
from pathlib import Path

SYSTEM = (Path(__file__).parent.parent / "prompts" / "system.md").read_text()


@dataclass
class History:
    messages: list[dict] = field(default_factory=list)

    def add_user(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str):
        self.messages.append({"role": "assistant", "content": content})

    def get(self) -> list[dict]:
        return [{"role": "system", "content": SYSTEM}] + self.messages

    def clear(self):
        self.messages = []
