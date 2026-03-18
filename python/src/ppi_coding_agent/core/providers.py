"""Provider bootstrap helpers for the coding-agent layer."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from ppi_ai import Model, get_provider, register_provider
from ppi_ai.providers import AzureOpenAIResponsesProvider, BedrockProvider, MistralProvider
from ppi_ai.providers.anthropic import AnthropicProvider
from ppi_ai.providers.openai_completions import OpenAICompletionsProvider
from ppi_ai.providers.openai_responses import OpenAIResponsesProvider


@dataclass(slots=True)
class ProviderRoute:
    """An explicit mapping from a logical provider key to a concrete adapter."""

    provider: str
    api: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderRegistryConfig:
    """Configurable provider registry for OpenAI-compatible and other adapters."""

    routes: dict[str, ProviderRoute] = field(default_factory=dict)
    default_route: ProviderRoute | None = None

    @classmethod
    def load(cls, source: str | None = None) -> "ProviderRegistryConfig":
        """Load provider routes from JSON or from environment variables.

        Supported inputs:
        - `source` or `PI_PROVIDER_REGISTRY_FILE`: path to a JSON file.
        - `PI_PROVIDER_REGISTRY`: JSON object with `routes` and optional `default`.

        The route keys are typically provider names such as `openai` or compound
        keys such as `openai:openai-responses`.
        """

        payload = _load_registry_payload(source)
        if not payload:
            return cls()

        routes: dict[str, ProviderRoute] = {}
        for key, value in (payload.get("routes") or {}).items():
            if not isinstance(value, dict):
                continue
            routes[str(key)] = ProviderRoute(
                provider=str(value.get("provider", key)),
                api=value.get("api"),
                base_url=value.get("base_url"),
                api_key=value.get("api_key"),
                headers=dict(value.get("headers", {}) or {}),
                metadata=dict(value.get("metadata", {}) or {}),
            )

        default_value = payload.get("default")
        default_route = None
        if isinstance(default_value, dict):
            default_route = ProviderRoute(
                provider=str(default_value.get("provider", "")),
                api=default_value.get("api"),
                base_url=default_value.get("base_url"),
                api_key=default_value.get("api_key"),
                headers=dict(default_value.get("headers", {}) or {}),
                metadata=dict(default_value.get("metadata", {}) or {}),
            )

        return cls(routes=routes, default_route=default_route)

    def resolve(self, model: Model | None) -> ProviderRoute | None:
        if model is None:
            return self.default_route
        candidates = [
            f"{model.provider}:{model.api}",
            model.provider,
            model.api,
        ]
        for key in candidates:
            route = self.routes.get(key)
            if route is not None:
                return route
        return self.default_route


@dataclass(slots=True)
class ProviderBootstrapResult:
    model_provider: str
    registered: bool = False
    provider_name: str | None = None
    provider_api: str | None = None
    api_key: str | None = None
    resolved_model: Model | None = None


def ensure_provider_registered(
    model: Model | None,
    registry_config: ProviderRegistryConfig | None = None,
) -> ProviderBootstrapResult:
    if model is None:
        return ProviderBootstrapResult(model_provider="")

    registry_config = registry_config or ProviderRegistryConfig.load()
    route = registry_config.resolve(model)

    resolved_model = model
    if route is not None:
        if route.provider and route.provider != model.provider:
            resolved_model = replace(resolved_model, provider=route.provider)
        if route.api and route.api != resolved_model.api:
            resolved_model = replace(resolved_model, api=route.api)
        if route.base_url and route.base_url != resolved_model.base_url:
            resolved_model = replace(resolved_model, base_url=route.base_url)

    provider_name = resolved_model.provider or ""
    if not provider_name:
        return ProviderBootstrapResult(model_provider="", resolved_model=resolved_model)

    if _provider_available(provider_name):
        return ProviderBootstrapResult(
            model_provider=provider_name,
            registered=False,
            provider_name=provider_name,
            provider_api=resolved_model.api,
            api_key=route.api_key if route else None,
            resolved_model=resolved_model,
        )

    provider = _build_provider(resolved_model, route)
    if provider is None:
        return ProviderBootstrapResult(
            model_provider=provider_name,
            registered=False,
            resolved_model=resolved_model,
        )

    register_provider(provider_name, provider)
    return ProviderBootstrapResult(
        model_provider=provider_name,
        registered=True,
        provider_name=provider_name,
        provider_api=getattr(provider, "api", None),
        api_key=route.api_key if route else None,
        resolved_model=resolved_model,
    )


def _load_registry_payload(source: str | None = None) -> dict[str, Any]:
    raw = os.getenv("PI_PROVIDER_REGISTRY")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            return {}

    path = source or os.getenv("PI_PROVIDER_REGISTRY_FILE")
    if path:
        file_path = Path(path)
        if file_path.exists():
            try:
                return json.loads(file_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}


def _provider_available(name: str) -> bool:
    try:
        get_provider(name)
        return True
    except Exception:
        return False


def _build_provider(model: Model, route: ProviderRoute | None = None) -> Any | None:
    provider_name = model.provider.lower()
    api_name = (route.api if route and route.api else model.api).lower()
    if provider_name == "openai":
        if api_name == "openai-responses":
            return OpenAIResponsesProvider()
        return OpenAICompletionsProvider()
    if provider_name == "anthropic":
        return AnthropicProvider()
    if provider_name == "azure-openai-responses":
        return AzureOpenAIResponsesProvider()
    if provider_name == "mistral":
        return MistralProvider()
    if provider_name in {"bedrock", "amazon-bedrock"}:
        return BedrockProvider()
    if model.base_url and api_name == "openai-responses":
        return OpenAIResponsesProvider()
    if model.base_url:
        return OpenAICompletionsProvider()
    return None
