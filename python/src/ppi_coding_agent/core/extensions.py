"""Extension runtime and hook contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import (
    ExtensionContext,
    ExtensionDefinition,
    ExtensionEvent,
    ExtensionHookType,
    ExtensionRuntime,
    ExtensionRunner,
    ExtensionType,
    LoadExtensionsResult,
)


@dataclass(slots=True)
class InMemoryExtensionRuntime:
    registry: dict[str, Any] = field(default_factory=dict)

    def register_tool(self, name: str, tool: Any) -> None:
        self.registry[name] = tool

    def register_command(self, name: str, handler: Any) -> None:
        self.registry[name] = handler

    def register_provider(self, name: str, provider: Any) -> None:
        self.registry[name] = provider

    def register_flag(self, name: str, handler: Any) -> None:
        self.registry[name] = handler

    def register_shortcut(self, name: str, handler: Any) -> None:
        self.registry[name] = handler

    def register_renderer(self, name: str, renderer: Any) -> None:
        self.registry[name] = renderer

    def unregister(self, name: str) -> None:
        self.registry.pop(name, None)

    def get(self, name: str) -> Any | None:
        return self.registry.get(name)

    def list(self) -> list[str]:
        return sorted(self.registry.keys())


@dataclass(slots=True)
class InMemoryExtensionRunner:
    runtime: InMemoryExtensionRuntime = field(default_factory=InMemoryExtensionRuntime)
    context: ExtensionContext | None = None
    extensions: list[ExtensionDefinition] = field(default_factory=list)
    events: list[ExtensionEvent] = field(default_factory=list)
    loaded: bool = False

    def emit(self, event: ExtensionEvent) -> None:
        self.events.append(event)

    def load(self) -> None:
        self.loaded = True
        for extension in self.extensions:
            self.emit(ExtensionEvent(type="load", payload={"kind": extension.kind, "name": extension.name}, extension_name=extension.name))
            self._register_extension(extension)

    def reload(self) -> LoadExtensionsResult:
        self.runtime = InMemoryExtensionRuntime(registry=dict(self.runtime.registry))
        self.events.clear()
        self.load()
        return LoadExtensionsResult(loaded=[ext.name for ext in self.extensions], warnings=[], errors=[], skipped=[])

    def get_runtime(self) -> ExtensionRuntime:
        return self.runtime

    def bind(self, context: ExtensionContext) -> None:
        self.context = context

    def shutdown(self) -> None:
        self.emit(ExtensionEvent(type="shutdown", payload={}, extension_name=None))
        self.loaded = False

    def add_extension(self, extension: ExtensionDefinition) -> None:
        self.extensions.append(extension)
        if self.loaded:
            self._register_extension(extension)

    def _register_extension(self, extension: ExtensionDefinition) -> None:
        payload = {"definition": extension, "context": self.context}
        if extension.kind == "tool":
            self.runtime.register_tool(extension.name, payload)
        elif extension.kind == "command":
            self.runtime.register_command(extension.name, payload)
        elif extension.kind == "shortcut":
            self.runtime.register_shortcut(extension.name, payload)
        elif extension.kind == "flag":
            self.runtime.register_flag(extension.name, payload)
        elif extension.kind == "renderer":
            self.runtime.register_renderer(extension.name, payload)
        elif extension.kind == "provider":
            self.runtime.register_provider(extension.name, payload)


def _extension_to_dict(extension: ExtensionDefinition) -> dict[str, Any]:
    return {
        "name": extension.name,
        "kind": extension.kind,
        "path": extension.path,
        "metadata": extension.metadata,
    }


def _extension_from_dict(data: dict[str, Any]) -> ExtensionDefinition:
    return ExtensionDefinition(
        name=data.get("name", ""),
        kind=data.get("kind", "hook"),
        path=data.get("path"),
        metadata=data.get("metadata", {}) or {},
    )


@dataclass(slots=True)
class FileExtensionRunner(InMemoryExtensionRunner):
    manifest_path: Path | None = None
    autosave: bool = True

    def load(self) -> None:
        if self.manifest_path is not None and self.manifest_path.exists():
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            self.extensions = [_extension_from_dict(item) for item in data.get("extensions", []) if isinstance(item, dict)]
        InMemoryExtensionRunner.load(self)
        if self.autosave:
            self.save()

    def reload(self) -> LoadExtensionsResult:
        self.runtime = InMemoryExtensionRuntime()
        self.events.clear()
        self.loaded = False
        self.load()
        return LoadExtensionsResult(loaded=[ext.name for ext in self.extensions], warnings=[], errors=[], skipped=[])

    def add_extension(self, extension: ExtensionDefinition) -> None:
        InMemoryExtensionRunner.add_extension(self, extension)
        if self.autosave:
            self.save()

    def shutdown(self) -> None:
        InMemoryExtensionRunner.shutdown(self)
        if self.autosave:
            self.save()

    def save(self) -> None:
        if self.manifest_path is None:
            return None
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"extensions": [_extension_to_dict(ext) for ext in self.extensions]}
        self.manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
