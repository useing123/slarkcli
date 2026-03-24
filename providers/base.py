from typing import Protocol, Sequence, runtime_checkable

from providers.types import ProviderResponse


@runtime_checkable
class BaseProvider(Protocol):
    model: str

    async def complete(
        self,
        messages: Sequence[dict],
        tools: Sequence[dict] | None,
        stream: bool = False,
    ) -> ProviderResponse: ...
