"""Extension protocol and dataclass definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeAlias


ExtensionType = Literal["tool", "command", "shortcut", "flag", "renderer", "provider", "hook"]
ExtensionHookType: TypeAlias = Literal[
    "before_agent_start",
    "after_agent_end",
    "before_turn",
    "after_turn",
    "before_tool_call",
    "after_tool_call",
    "before_provider_request",
    "context_mutation",
    "session_start",
    "session_shutdown",
]


@dataclass(slots=True)
class ExtensionEvent:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    extension_name: str | None = None


@dataclass(slots=True)
class LoadExtensionsResult:
    loaded: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExtensionDefinition:
    name: str
    kind: ExtensionType
    path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExtensionContext:
    cwd: str = ""
    agent_dir: str = ""
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ExtensionRuntime(Protocol):
    def register_tool(self, name: str, tool: Any) -> None:
        ...

    def register_command(self, name: str, handler: Any) -> None:
        ...

    def register_provider(self, name: str, provider: Any) -> None:
        ...

    def register_flag(self, name: str, handler: Any) -> None:
        ...

    def register_shortcut(self, name: str, handler: Any) -> None:
        ...

    def register_renderer(self, name: str, renderer: Any) -> None:
        ...

    def unregister(self, name: str) -> None:
        ...

    def get(self, name: str) -> Any | None:
        ...

    def list(self) -> list[str]:
        ...


class ExtensionRunner(Protocol):
    def emit(self, event: ExtensionEvent) -> None:
        ...

    def load(self) -> None:
        ...

    def reload(self) -> LoadExtensionsResult:
        ...

    def get_runtime(self) -> ExtensionRuntime:
        ...

    def bind(self, context: ExtensionContext) -> None:
        ...

    def shutdown(self) -> None:
        ...

    def add_extension(self, extension: ExtensionDefinition) -> None:
        ...


__all__ = [
    "ExtensionContext",
    "ExtensionDefinition",
    "ExtensionEvent",
    "ExtensionHookType",
    "ExtensionRuntime",
    "ExtensionRunner",
    "ExtensionType",
    "LoadExtensionsResult",
]
