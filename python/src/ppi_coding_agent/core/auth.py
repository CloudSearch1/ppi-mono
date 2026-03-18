"""Authentication storage contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import AuthStorage, AuthStorageData, CredentialRecord


@dataclass(slots=True)
class FileAuthStorage:
    path: Path
    data: AuthStorageData = field(default_factory=AuthStorageData)

    def get_api_key(self, provider: str) -> str | None:
        value = self.data.credentials.get(provider)
        if isinstance(value, dict):
            return value.get("api_key")
        if isinstance(value, str):
            return value
        return None

    def set_api_key(self, provider: str, api_key: str | None) -> None:
        if api_key is None:
            self.data.credentials.pop(provider, None)
        else:
            self.data.credentials[provider] = {"api_key": api_key}
        self.save()

    def delete_api_key(self, provider: str) -> None:
        self.data.credentials.pop(provider, None)
        self.save()

    def list_providers(self) -> list[str]:
        return sorted(self.data.credentials.keys())

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump({"credentials": self.data.credentials}, handle, indent=2, ensure_ascii=False)


@dataclass(slots=True)
class MemoryAuthStorage:
    data: AuthStorageData = field(default_factory=AuthStorageData)

    def get_api_key(self, provider: str) -> str | None:
        value = self.data.credentials.get(provider)
        if isinstance(value, dict):
            return value.get("api_key")
        if isinstance(value, str):
            return value
        return None

    def set_api_key(self, provider: str, api_key: str | None) -> None:
        if api_key is None:
            self.data.credentials.pop(provider, None)
        else:
            self.data.credentials[provider] = {"api_key": api_key}

    def delete_api_key(self, provider: str) -> None:
        self.data.credentials.pop(provider, None)

    def list_providers(self) -> list[str]:
        return sorted(self.data.credentials.keys())

    def save(self) -> None:
        return None
