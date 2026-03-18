"""Settings hierarchy for the coding-agent layer."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import Settings, SettingsLoadResult, SettingsManager, SettingsScope, SettingsStorage
from .helpers import get_nested, merge_dicts


@dataclass(slots=True)
class InMemorySettingsManager:
    global_settings: Settings = field(default_factory=Settings)
    project_settings: Settings = field(default_factory=Settings)

    def get_global_settings(self) -> Settings:
        return self.global_settings

    def get_project_settings(self) -> Settings:
        return self.project_settings

    def get_effective_settings(self) -> Settings:
        merged = Settings()
        for key in merged.__dataclass_fields__:
            global_value = getattr(self.global_settings, key)
            project_value = getattr(self.project_settings, key)
            if isinstance(global_value, dict) and isinstance(project_value, dict):
                setattr(merged, key, merge_dicts(global_value, project_value))
            else:
                setattr(merged, key, project_value or global_value)
        return merged

    def get_default_model(self) -> str | None:
        return get_nested(self.get_effective_settings(), "model.default")

    def get_default_provider(self) -> str | None:
        return get_nested(self.get_effective_settings(), "model.provider")

    def get_default_thinking_level(self) -> str | None:
        return get_nested(self.get_effective_settings(), "thinking.level")

    def get_block_images(self) -> bool:
        return bool(get_nested(self.get_effective_settings(), "markdown.block_images", False))

    def get_transport(self) -> str | None:
        return get_nested(self.get_effective_settings(), "transport.default")

    def get_session_dir(self) -> str | None:
        return get_nested(self.get_effective_settings(), "resources.session_dir")

    def get_terminal_settings(self) -> dict[str, Any]:
        value = get_nested(self.get_effective_settings(), "terminal", {})
        return value if isinstance(value, dict) else {}

    def get_resource_settings(self) -> dict[str, Any]:
        value = get_nested(self.get_effective_settings(), "resources", {})
        return value if isinstance(value, dict) else {}

    def get_extension_settings(self) -> dict[str, Any]:
        value = get_nested(self.get_effective_settings(), "extensions", {})
        return value if isinstance(value, dict) else {}

    def set_global_settings(self, settings: Settings) -> None:
        self.global_settings = settings

    def set_project_settings(self, settings: Settings) -> None:
        self.project_settings = settings

    def migrate(self) -> None:
        return None

    def reload(self) -> None:
        return None

    def save(self) -> None:
        return None


def _settings_to_dict(settings: Settings) -> dict[str, Any]:
    return {
        "version": 1,
        "model": dict(settings.model),
        "thinking": dict(settings.thinking),
        "transport": dict(settings.transport),
        "compaction": dict(settings.compaction),
        "retry": dict(settings.retry),
        "terminal": dict(settings.terminal),
        "markdown": dict(settings.markdown),
        "resources": dict(settings.resources),
        "extensions": dict(settings.extensions),
        "skills": dict(settings.skills),
        "prompts": dict(settings.prompts),
        "themes": dict(settings.themes),
        "packages": dict(settings.packages),
    }


def _settings_from_dict(data: dict[str, Any] | None) -> Settings:
    data = data or {}
    allowed = {field_name for field_name in Settings.__dataclass_fields__}
    payload = {key: value for key, value in data.items() if key in allowed and isinstance(value, dict)}
    return Settings(**payload)


@dataclass(slots=True)
class FileSettingsManager:
    global_path: Path
    project_path: Path | None = None
    global_settings: Settings = field(default_factory=Settings)
    project_settings: Settings = field(default_factory=Settings)

    def __post_init__(self) -> None:
        self.reload()

    def get_global_settings(self) -> Settings:
        return self.global_settings

    def get_project_settings(self) -> Settings:
        return self.project_settings

    def get_effective_settings(self) -> Settings:
        return InMemorySettingsManager(self.global_settings, self.project_settings).get_effective_settings()

    def get_default_model(self) -> str | None:
        return InMemorySettingsManager(self.global_settings, self.project_settings).get_default_model()

    def get_default_provider(self) -> str | None:
        return InMemorySettingsManager(self.global_settings, self.project_settings).get_default_provider()

    def get_default_thinking_level(self) -> str | None:
        return InMemorySettingsManager(self.global_settings, self.project_settings).get_default_thinking_level()

    def get_block_images(self) -> bool:
        return InMemorySettingsManager(self.global_settings, self.project_settings).get_block_images()

    def get_transport(self) -> str | None:
        return InMemorySettingsManager(self.global_settings, self.project_settings).get_transport()

    def get_session_dir(self) -> str | None:
        return InMemorySettingsManager(self.global_settings, self.project_settings).get_session_dir()

    def get_terminal_settings(self) -> dict[str, Any]:
        return InMemorySettingsManager(self.global_settings, self.project_settings).get_terminal_settings()

    def get_resource_settings(self) -> dict[str, Any]:
        return InMemorySettingsManager(self.global_settings, self.project_settings).get_resource_settings()

    def get_extension_settings(self) -> dict[str, Any]:
        return InMemorySettingsManager(self.global_settings, self.project_settings).get_extension_settings()

    def set_global_settings(self, settings: Settings) -> None:
        self.global_settings = settings
        self.save()

    def set_project_settings(self, settings: Settings) -> None:
        self.project_settings = settings
        self.save()

    def migrate(self) -> None:
        self.reload()

    def reload(self) -> None:
        if self.global_path.exists():
            self.global_settings = _settings_from_dict(json.loads(self.global_path.read_text(encoding="utf-8")))
        if self.project_path is not None and self.project_path.exists():
            self.project_settings = _settings_from_dict(json.loads(self.project_path.read_text(encoding="utf-8")))

    def save(self) -> None:
        self.global_path.parent.mkdir(parents=True, exist_ok=True)
        self.global_path.write_text(json.dumps(_settings_to_dict(self.global_settings), indent=2, ensure_ascii=False), encoding="utf-8")
        if self.project_path is not None:
            self.project_path.parent.mkdir(parents=True, exist_ok=True)
            self.project_path.write_text(json.dumps(_settings_to_dict(self.project_settings), indent=2, ensure_ascii=False), encoding="utf-8")
