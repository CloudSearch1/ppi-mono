"""Sandbox runtime provider contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class SandboxRuntimeProvider(Protocol):
    def get_data(self) -> dict[str, Any]:
        ...

    def get_runtime(self) -> dict[str, Any]:
        ...

    def handle_message(self, message: dict[str, Any]) -> Any:
        ...

    def get_description(self) -> str:
        ...


@dataclass(slots=True)
class SandboxUrlProvider:
    url: str

