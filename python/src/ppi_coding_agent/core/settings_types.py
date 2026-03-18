"""Settings protocol and dataclass definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeAlias


SettingsScope: TypeAlias = Literal["global", "project"]


@dataclass(slots=True)
class Settings:
    model: dict[str, Any] = field(default_factory=dict)
    thinking: dict[str, Any] = field(default_factory=dict)
    transport: dict[str, Any] = field(default_factory=dict)
    compaction: dict[str, Any] = field(default_factory=dict)
    retry: dict[str, Any] = field(default_factory=dict)
    terminal: dict[str, Any] = field(default_factory=dict)
    markdown: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)
    skills: dict[str, Any] = field(default_factory=dict)
    prompts: dict[str, Any] = field(default_factory=dict)
    themes: dict[str, Any] = field(default_factory=dict)
    packages: dict[str, Any] = field(default_factory=dict)


class SettingsStorage(Protocol):
    def with_lock(self, scope: SettingsScope, fn: Any) -> None:
        ...


@dataclass(slots=True)
class SettingsLoadResult:
    scope: SettingsScope
    settings: Settings
    error: str | None = None


class SettingsManager(Protocol):
    def get_global_settings(self) -> Settings:
        ...

    def get_project_settings(self) -> Settings:
        ...

    def get_effective_settings(self) -> Settings:
        ...

    def get_default_model(self) -> str | None:
        ...

    def get_default_provider(self) -> str | None:
        ...

    def get_default_thinking_level(self) -> str | None:
        ...

    def get_block_images(self) -> bool:
        ...

    def get_transport(self) -> str | None:
        ...

    def get_session_dir(self) -> str | None:
        ...

    def get_terminal_settings(self) -> dict[str, Any]:
        ...

    def get_resource_settings(self) -> dict[str, Any]:
        ...

    def get_extension_settings(self) -> dict[str, Any]:
        ...

    def set_global_settings(self, settings: Settings) -> None:
        ...

    def set_project_settings(self, settings: Settings) -> None:
        ...

    def migrate(self) -> None:
        ...

    def reload(self) -> None:
        ...

    def save(self) -> None:
        ...


__all__ = ["Settings", "SettingsLoadResult", "SettingsManager", "SettingsScope", "SettingsStorage"]
