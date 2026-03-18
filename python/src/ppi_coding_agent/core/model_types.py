"""Model registry and message-related type definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeAlias

from ppi_ai import AssistantMessage, ImageContent, Message, Model, TextContent, ThinkingContent, ToolCall, ToolResultMessage, UserMessage


ModelSelectionMode: TypeAlias = Literal["default", "restored", "explicit", "fallback"]


@dataclass(slots=True)
class ModelRegistryEntry:
    provider: str
    model_id: str
    display_name: str | None = None
    override: dict[str, Any] = field(default_factory=dict)
    api: str | None = None
    thinking_level: str | None = None
    base_url: str | None = None


@dataclass(slots=True)
class ModelRegistryResult:
    model: Model | None = None
    fallback_message: str | None = None
    mode: ModelSelectionMode = "default"


class ModelRegistry(Protocol):
    def get_model(self, provider: str, model_id: str) -> Model:
        ...

    def list_models(self, provider: str | None = None) -> list[Model]:
        ...

    def register_provider(self, provider: str, payload: Any) -> None:
        ...

    def unregister_provider(self, provider: str) -> None:
        ...

    def find(self, provider: str, model_id: str) -> Model | None:
        ...

    def resolve_default(self) -> Model | None:
        ...

    def resolve_model(self, provider: str | None = None, model_id: str | None = None) -> Model | None:
        ...

    def resolve_scoped_models(self) -> list[Model]:
        ...

    def set_default_provider(self, provider: str | None) -> None:
        ...

    def set_default_model(self, model_id: str | None) -> None:
        ...

    async def get_api_key(self, model: Model) -> str | None:
        ...


__all__ = [
    "AssistantMessage",
    "ImageContent",
    "Message",
    "Model",
    "ModelRegistry",
    "ModelRegistryEntry",
    "ModelRegistryResult",
    "ModelSelectionMode",
    "TextContent",
    "ThinkingContent",
    "ToolCall",
    "ToolResultMessage",
    "UserMessage",
]
