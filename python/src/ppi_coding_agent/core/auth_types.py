"""Authentication protocol and dataclass definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class AuthStorageData:
    credentials: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CredentialRecord:
    provider: str
    api_key: str | None = None
    oauth_token: str | None = None
    refresh_token: str | None = None
    expires_at: int | None = None


class AuthStorage(Protocol):
    def get_api_key(self, provider: str) -> str | None:
        ...

    def set_api_key(self, provider: str, api_key: str | None) -> None:
        ...

    def delete_api_key(self, provider: str) -> None:
        ...

    def list_providers(self) -> list[str]:
        ...

    def save(self) -> None:
        ...


__all__ = ["AuthStorage", "AuthStorageData", "CredentialRecord"]
