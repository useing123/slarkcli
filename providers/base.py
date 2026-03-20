from typing import Protocol, runtime_checkable


@runtime_checkable
class BaseProvider(Protocol):
    model: str

    async def complete(self, messages: list[dict], tools: list[dict]) -> dict: ...
