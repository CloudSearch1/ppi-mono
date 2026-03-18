"""Resource discovery and loading contracts."""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from .types import ResourceCollision, ResourceDiagnostic, ResourceGroup, ResourceItem, ResourceKind, ResourceLoadResult, ResourceLoader
from .helpers import infer_kind_from_path


@dataclass(slots=True)
class InMemoryResourceLoader:
    roots: list[Path] = field(default_factory=list)
    diagnostics: list[ResourceDiagnostic] = field(default_factory=list)
    collisions: list[ResourceCollision] = field(default_factory=list)
    resources: dict[str, list[ResourceItem]] = field(default_factory=dict)

    def load(self) -> ResourceLoadResult:
        self.diagnostics.clear()
        self.collisions.clear()
        self.resources.clear()
        for root in self.roots:
            if not root.exists():
                self.diagnostics.append(
                    ResourceDiagnostic(kind="config", path=str(root), message="resource root does not exist", severity="warning")
                )
                continue
            if root.is_file():
                kind = infer_kind_from_path(root)
                self.resources.setdefault(kind, []).append(
                    ResourceItem(kind=kind, path=str(root), name=root.stem, source="filesystem")
                )
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                kind = infer_kind_from_path(path)
                item = ResourceItem(kind=kind, path=str(path), name=path.stem, source="filesystem")
                existing = next((resource for resource in self.resources.get(kind, []) if resource.name == item.name), None)
                if existing is not None:
                    self.collisions.append(
                        ResourceCollision(kind=kind, path=str(path), existing=existing, incoming=item)
                    )
                self.resources.setdefault(kind, []).append(item)
        return ResourceLoadResult(resources=self.resources, diagnostics=list(self.diagnostics), collisions=list(self.collisions))

    def reload(self) -> ResourceLoadResult:
        return self.load()

    def get_diagnostics(self) -> list[ResourceDiagnostic]:
        return list(self.diagnostics)

    def list_resources(self, kind: ResourceKind | None = None) -> list[ResourceItem]:
        if kind is None:
            items: list[ResourceItem] = []
            for resources in self.resources.values():
                items.extend(resources)
            return items
        return list(self.resources.get(kind, []))

    def get_groups(self) -> list[ResourceGroup]:
        return [ResourceGroup(kind=kind, items=list(items)) for kind, items in self.resources.items()]

    def load_path(self, path: str, kind: ResourceKind) -> ResourceGroup:
        item_path = Path(path)
        item = ResourceItem(kind=kind, path=str(item_path), name=item_path.stem, source="filesystem")
        group = ResourceGroup(kind=kind, items=[item])
        self.resources.setdefault(kind, []).append(item)
        return group


def _resource_item_to_dict(item: ResourceItem) -> dict[str, Any]:
    return {
        "kind": item.kind,
        "path": item.path,
        "name": item.name,
        "source": item.source,
        "metadata": item.metadata,
    }


def _resource_item_from_dict(data: dict[str, Any]) -> ResourceItem:
    return ResourceItem(
        kind=data.get("kind", "config"),
        path=data.get("path", ""),
        name=data.get("name", ""),
        source=data.get("source", "filesystem"),
        metadata=data.get("metadata", {}) or {},
    )


@dataclass(slots=True)
class FileResourceLoader(InMemoryResourceLoader):
    manifest_path: Path | None = None
    autosave: bool = True

    def load(self) -> ResourceLoadResult:
        if self.manifest_path is not None and self.manifest_path.exists():
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            self.diagnostics = [
                ResourceDiagnostic(**item) for item in data.get("diagnostics", [])
                if isinstance(item, dict)
            ]
            self.collisions = [
                ResourceCollision(kind=item.get("kind", "config"), path=item.get("path", ""), existing=item.get("existing"), incoming=item.get("incoming"))
                for item in data.get("collisions", [])
                if isinstance(item, dict)
            ]
            self.resources = {}
            for kind, items in (data.get("resources") or {}).items():
                self.resources[kind] = [_resource_item_from_dict(item) for item in items if isinstance(item, dict)]
            return ResourceLoadResult(resources=self.resources, diagnostics=list(self.diagnostics), collisions=list(self.collisions))
        result = InMemoryResourceLoader.load(self)
        if self.autosave:
            self.save()
        return result

    def reload(self) -> ResourceLoadResult:
        return self.load()

    def save(self) -> None:
        if self.manifest_path is None:
            return None
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "resources": {kind: [_resource_item_to_dict(item) for item in items] for kind, items in self.resources.items()},
            "diagnostics": [item.__dict__ if hasattr(item, "__dict__") else {"kind": item.kind, "path": item.path, "message": item.message, "severity": item.severity} for item in self.diagnostics],
            "collisions": [
                {
                    "kind": item.kind,
                    "path": item.path,
                    "existing": item.existing,
                    "incoming": item.incoming,
                }
                for item in self.collisions
            ],
        }
        self.manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
