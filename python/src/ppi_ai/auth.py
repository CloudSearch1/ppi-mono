"""Authentication and API key lookup contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Protocol, TypeAlias


class ApiKeySource(Protocol):
    def get(self, provider: str) -> str | None:
        ...


@dataclass(slots=True)
class OAuthCredential:
    provider: str
    token: str
    refresh_token: str | None = None
    expires_at: int | None = None


OAuthProvider: TypeAlias = str


@dataclass(slots=True)
class EnvironmentApiKeySource:
    """Resolve provider API keys from environment variables."""

    env_map: dict[str, str] = field(default_factory=dict)

    def get(self, provider: str) -> str | None:
        env_name = self.env_map.get(provider)
        if env_name:
            value = os.getenv(env_name)
            if value:
                return value

        candidate_names = (
            f"{provider.upper()}_API_KEY",
            f"{provider.upper()}_TOKEN",
            "OPENAI_API_KEY" if provider == "openai" else None,
        )
        for name in candidate_names:
            if not name:
                continue
            value = os.getenv(name)
            if value:
                return value
        return None
