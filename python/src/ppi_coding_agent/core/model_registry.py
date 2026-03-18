"""Model registry and provider resolution."""

from __future__ import annotations

import os
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any

from ppi_ai import Model

from .types import ModelRegistry, ModelRegistryEntry, ModelRegistryResult, ModelSelectionMode


@dataclass(slots=True)
class InMemoryModelRegistry:
    providers: dict[str, dict[str, Model]] = field(default_factory=dict)
    default_provider: str | None = None
    default_model_id: str | None = None

    def get_model(self, provider: str, model_id: str) -> Model:
        model = self.find(provider, model_id)
        if model is None:
            raise KeyError(f"Unknown model: {provider}/{model_id}")
        return model

    def list_models(self, provider: str | None = None) -> list[Model]:
        if provider is not None:
            return list(self.providers.get(provider, {}).values())
        models: list[Model] = []
        for provider_models in self.providers.values():
            models.extend(provider_models.values())
        return models

    def register_provider(self, provider: str, payload: Any) -> None:
        provider_models = self.providers.setdefault(provider, {})
        if isinstance(payload, Model):
            provider_models[payload.id] = payload
            return
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, Model):
                    provider_models[item.id] = item
            return
        if isinstance(payload, dict):
            models = payload.get("models") or []
            for item in models:
                if isinstance(item, Model):
                    provider_models[item.id] = item
                elif isinstance(item, dict) and item.get("id"):
                    provider_models[item["id"]] = Model(
                        provider=provider,
                        api=item.get("api", provider),
                        id=item["id"],
                        name=item.get("name"),
                        base_url=item.get("base_url"),
                    )

    def unregister_provider(self, provider: str) -> None:
        self.providers.pop(provider, None)

    def find(self, provider: str, model_id: str) -> Model | None:
        return self.providers.get(provider, {}).get(model_id)

    def resolve_default(self) -> Model | None:
        if self.default_provider and self.default_model_id:
            return self.find(self.default_provider, self.default_model_id)
        if self.default_provider:
            provider_models = self.providers.get(self.default_provider, {})
            return next(iter(provider_models.values()), None)
        for provider_models in self.providers.values():
            model = next(iter(provider_models.values()), None)
            if model is not None:
                return model
        return None

    def resolve_model(self, provider: str | None = None, model_id: str | None = None) -> Model | None:
        if provider and model_id:
            return self.find(provider, model_id)
        if provider:
            provider_models = self.providers.get(provider, {})
            if model_id is not None:
                return provider_models.get(model_id)
            return next(iter(provider_models.values()), None)
        if model_id:
            for provider_models in self.providers.values():
                if model_id in provider_models:
                    return provider_models[model_id]
        return self.resolve_default()

    def resolve_scoped_models(self) -> list[Model]:
        return self.list_models()

    def set_default_provider(self, provider: str | None) -> None:
        self.default_provider = provider

    def set_default_model(self, model_id: str | None) -> None:
        self.default_model_id = model_id

    async def get_api_key(self, model: Model) -> str | None:
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "azure-openai-responses": "AZURE_OPENAI_API_KEY",
        }
        env_var = env_map.get(model.provider, f"{model.provider.upper()}_API_KEY")
        value = os.getenv(env_var)
        return value if value else None


def _model_to_dict(model: Model) -> dict[str, Any]:
    compat = model.compat
    return {
        "provider": model.provider,
        "api": model.api,
        "id": model.id,
        "name": model.name,
        "base_url": model.base_url,
        "reasoning": model.reasoning,
        "input": list(model.input),
        "output": list(model.output),
        "context_window": model.context_window,
        "max_output_tokens": model.max_output_tokens,
        "compat": asdict(compat) if compat is not None and is_dataclass(compat) else None,
    }


def _model_from_dict(data: dict[str, Any]) -> Model:
    return Model(
        provider=data.get("provider", ""),
        api=data.get("api", data.get("provider", "")),
        id=data.get("id", ""),
        name=data.get("name"),
        base_url=data.get("base_url"),
        reasoning=bool(data.get("reasoning", False)),
        input=list(data.get("input", []) or []),
        output=list(data.get("output", []) or []),
        context_window=data.get("context_window"),
        max_output_tokens=data.get("max_output_tokens"),
    )


@dataclass(slots=True)
class FileModelRegistry(InMemoryModelRegistry):
    path: Path | None = None
    autosave: bool = True

    def __post_init__(self) -> None:
        self.reload()

    def register_provider(self, provider: str, payload: Any) -> None:
        InMemoryModelRegistry.register_provider(self, provider, payload)
        if self.autosave:
            self.save()

    def unregister_provider(self, provider: str) -> None:
        InMemoryModelRegistry.unregister_provider(self, provider)
        if self.autosave:
            self.save()

    def set_default_provider(self, provider: str | None) -> None:
        InMemoryModelRegistry.set_default_provider(self, provider)
        if self.autosave:
            self.save()

    def set_default_model(self, model_id: str | None) -> None:
        InMemoryModelRegistry.set_default_model(self, model_id)
        if self.autosave:
            self.save()

    def reload(self) -> None:
        if self.path is None or not self.path.exists():
            return None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.providers = {}
        for provider, models in (data.get("providers") or {}).items():
            self.providers[provider] = {}
            for model_data in models:
                if isinstance(model_data, dict):
                    model = _model_from_dict(model_data)
                    self.providers[provider][model.id] = model
        self.default_provider = data.get("default_provider")
        self.default_model_id = data.get("default_model_id")

    def save(self) -> None:
        if self.path is None:
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "default_provider": self.default_provider,
            "default_model_id": self.default_model_id,
            "providers": {
                provider: [_model_to_dict(model) for model in models.values()]
                for provider, models in self.providers.items()
            },
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
