"""Resource-related protocol and dataclass definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeAlias


ResourceKind: TypeAlias = Literal["skill", "prompt", "theme", "extension", "agent", "package", "config"]


@dataclass(slots=True)
class ResourceDiagnostic:
    kind: str
    path: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"


@dataclass(slots=True)
class ResourceCollision:
    kind: str
    path: str
    existing: Any | None = None
    incoming: Any | None = None


@dataclass(slots=True)
class ResourceItem:
    kind: ResourceKind
    path: str
    name: str
    source: str = "filesystem"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResourceGroup:
    kind: ResourceKind
    items: list[ResourceItem] = field(default_factory=list)


@dataclass(slots=True)
class ResourceLoadResult:
    resources: dict[str, list[ResourceItem]] = field(default_factory=dict)
    diagnostics: list[ResourceDiagnostic] = field(default_factory=list)
    collisions: list[ResourceCollision] = field(default_factory=list)


class ResourceLoader(Protocol):
    def load(self) -> ResourceLoadResult:
        ...

    def reload(self) -> ResourceLoadResult:
        ...

    def get_diagnostics(self) -> list[ResourceDiagnostic]:
        ...

    def list_resources(self, kind: ResourceKind | None = None) -> list[ResourceItem]:
        ...

    def get_groups(self) -> list[ResourceGroup]:
        ...

    def load_path(self, path: str, kind: ResourceKind) -> ResourceGroup:
        ...


__all__ = [
    "ResourceCollision",
    "ResourceDiagnostic",
    "ResourceGroup",
    "ResourceItem",
    "ResourceKind",
    "ResourceLoadResult",
    "ResourceLoader",
]
