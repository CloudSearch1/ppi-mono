"""Browser storage contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class StorageBackend(Protocol):
    def get(self, store_name: str, key: str) -> Any:
        ...

    def set(self, store_name: str, key: str, value: Any) -> None:
        ...

    def delete(self, store_name: str, key: str) -> None:
        ...


@dataclass(slots=True)
class SettingsStore:
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SessionStore:
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderKeyStore:
    values: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class CustomProvider:
    id: str
    name: str
    type: str
    base_url: str


@dataclass(slots=True)
class CustomProviderStore:
    values: dict[str, CustomProvider] = field(default_factory=dict)


@dataclass(slots=True)
class AppStorage:
    backend: StorageBackend | None = None
    settings: SettingsStore = field(default_factory=SettingsStore)
    provider_keys: ProviderKeyStore = field(default_factory=ProviderKeyStore)
    sessions: SessionStore = field(default_factory=SessionStore)
    custom_providers: CustomProviderStore = field(default_factory=CustomProviderStore)
