"""Artifacts panel and tool contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class Artifact:
    filename: str
    action: str
    content: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class ArtifactStore(Protocol):
    def reconstruct_from_messages(self, messages: list[Any]) -> None:
        ...


class ArtifactTool(Protocol):
    name: str

    def execute(self, params: dict[str, Any]) -> Any:
        ...
