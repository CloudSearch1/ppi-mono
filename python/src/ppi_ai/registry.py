"""Provider registry and protocol types."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol

from .events import AssistantMessageEvent
from .models import AssistantMessage, Context, Model, StreamOptions


class AssistantMessageStream(Protocol):
    def __aiter__(self) -> AsyncIterator[AssistantMessageEvent]:
        ...

    async def result(self) -> AssistantMessage:
        ...

    async def cancel(self) -> None:
        ...


class Provider(Protocol):
    name: str
    api: str

    async def stream(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessageStream:
        ...

    async def complete(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessage:
        ...


@dataclass(slots=True)
class ProviderRegistry:
    providers: dict[str, Provider] = field(default_factory=dict)

    def register(self, name: str, provider: Provider) -> None:
        self.providers[name] = provider

    def get(self, name: str) -> Provider:
        try:
            return self.providers[name]
        except KeyError as exc:
            raise KeyError(f"Unknown provider: {name}") from exc

    def has(self, name: str) -> bool:
        return name in self.providers

    def list(self) -> list[str]:
        return sorted(self.providers.keys())

    def clear(self) -> None:
        self.providers.clear()


ApiRegistry = ProviderRegistry

_registry = ProviderRegistry()


def register_provider(name: str, provider: Provider) -> None:
    _registry.register(name, provider)


def get_provider(name: str) -> Provider:
    return _registry.get(name)
