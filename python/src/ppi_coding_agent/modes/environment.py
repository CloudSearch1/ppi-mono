"""Shared runtime environment for coding-agent CLI modes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ppi_coding_agent.core.extensions import FileExtensionRunner
from ppi_coding_agent.core.model_registry import FileModelRegistry
from ppi_coding_agent.core.resource_loader import FileResourceLoader
from ppi_coding_agent.core.schemas import available_schemas, load_schema_registry, validate_schema
from ppi_coding_agent.core.session import InMemorySessionManager
from ppi_coding_agent.core.settings import FileSettingsManager
from ppi_coding_agent.core.session_types import SessionInfo

from .shared import ModeInvocation


@dataclass(slots=True)
class ModePaths:
    cwd: Path
    config_dir: Path
    session_dir: Path
    settings_global_path: Path
    settings_project_path: Path
    model_registry_path: Path
    resource_manifest_path: Path
    extensions_manifest_path: Path


@dataclass(slots=True)
class ModeEnvironment:
    paths: ModePaths
    settings: FileSettingsManager
    sessions: InMemorySessionManager
    model_registry: FileModelRegistry
    resources: FileResourceLoader
    extensions: FileExtensionRunner
    schemas: dict[str, Any]

    def describe(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        return {
            "cwd": snapshot["paths"]["cwd"],
            "config_dir": snapshot["paths"]["config_dir"],
            "session_dir": snapshot["paths"]["session_dir"],
            "default_model": snapshot["settings"]["model"].get("default"),
            "default_provider": snapshot["settings"]["model"].get("provider"),
            "thinking_level": snapshot["settings"]["thinking"].get("level"),
            "block_images": bool(snapshot["settings"]["markdown"].get("block_images", False)),
            "transport": snapshot["settings"]["transport"].get("default"),
            "session_name": snapshot["session"].get("info", {}).get("name"),
            "session_id": snapshot["session"].get("header", {}).get("id"),
            "session_messages": snapshot["session"].get("entry_count", 0),
            "resource_count": snapshot["resources"]["count"],
            "extension_count": snapshot["extensions"]["count"],
            "schema_count": snapshot["schemas"]["count"],
            "schemas": snapshot["schemas"]["names"],
        }

    def snapshot(self) -> dict[str, Any]:
        header = self.sessions.get_header()
        session_info: SessionInfo | None = self.sessions.get_session_info()
        effective_settings = self.settings.get_effective_settings()
        return {
            "paths": {
                "cwd": str(self.paths.cwd),
                "config_dir": str(self.paths.config_dir),
                "session_dir": str(self.paths.session_dir),
            },
            "settings": asdict(effective_settings),
            "session": {
                "header": asdict(header) if header is not None else None,
                "info": asdict(session_info) if session_info is not None else None,
                "entry_count": len(self.sessions.get_entries()),
                "leaf_id": self.sessions.get_leaf_id(),
            },
            "models": {
                "default_provider": self.model_registry.default_provider,
                "default_model_id": self.model_registry.default_model_id,
                "providers": sorted(self.model_registry.providers.keys()),
                "count": len(self.model_registry.list_models()),
            },
            "resources": {
                "count": len(self.resources.list_resources()),
                "kinds": sorted(self.resources.resources.keys()),
            },
            "extensions": {
                "count": len(self.extensions.get_runtime().list()),
                "names": self.extensions.get_runtime().list(),
            },
            "schemas": {
                "count": len(self.schemas.get("schemas", {})),
                "names": sorted(self.schemas.get("schemas", {}).keys()),
            },
        }

    def validate_schema(self, name: str, payload: Any) -> None:
        validate_schema(name, payload)

    def schema_names(self) -> list[str]:
        return available_schemas()

    def reload(self) -> None:
        self.settings.reload()
        self.model_registry.reload()
        self.resources.reload()
        self.extensions.reload()
        self.sessions.reload()


def build_mode_paths(invocation: ModeInvocation) -> ModePaths:
    cwd = Path(invocation.cwd or Path.cwd()).resolve()
    config_dir = Path(invocation.config_dir).resolve() if invocation.config_dir else cwd / ".ppi"
    session_dir = Path(invocation.session_dir).resolve() if invocation.session_dir else config_dir / "sessions"
    return ModePaths(
        cwd=cwd,
        config_dir=config_dir,
        session_dir=session_dir,
        settings_global_path=config_dir / "settings.global.json",
        settings_project_path=config_dir / "settings.project.json",
        model_registry_path=config_dir / "model-registry.json",
        resource_manifest_path=config_dir / "resources.json",
        extensions_manifest_path=config_dir / "extensions.json",
    )


def build_mode_environment(invocation: ModeInvocation) -> ModeEnvironment:
    paths = build_mode_paths(invocation)
    settings = FileSettingsManager(global_path=paths.settings_global_path, project_path=paths.settings_project_path)
    model_registry = FileModelRegistry(path=paths.model_registry_path)
    resources = FileResourceLoader(manifest_path=paths.resource_manifest_path)
    extensions = FileExtensionRunner(manifest_path=paths.extensions_manifest_path)
    sessions = InMemorySessionManager.continue_recent(str(paths.cwd), session_dir=str(paths.session_dir))
    schemas = load_schema_registry()
    return ModeEnvironment(
        paths=paths,
        settings=settings,
        sessions=sessions,
        model_registry=model_registry,
        resources=resources,
        extensions=extensions,
        schemas=schemas,
    )
