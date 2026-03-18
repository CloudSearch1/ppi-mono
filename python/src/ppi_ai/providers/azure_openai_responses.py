"""Azure OpenAI Responses provider adapter template."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from ..models import AssistantMessage, Context, Model, OpenAIResponsesCompat, StreamOptions
from ..registry import AssistantMessageStream
from .openai_responses import OpenAIResponsesProvider
from .common import ProviderRequest


DEFAULT_AZURE_API_VERSION = "v1"


@dataclass(slots=True)
class AzureOpenAIResponsesOptions(StreamOptions):
    reasoning_effort: str | None = None
    reasoning_summary: str | None = None
    azure_api_version: str | None = None
    azure_resource_name: str | None = None
    azure_base_url: str | None = None
    azure_deployment_name: str | None = None


@dataclass(slots=True)
class AzureOpenAIResponsesProvider(OpenAIResponsesProvider):
    name: str = "azure-openai-responses"
    api: str = "azure-openai-responses"
    compat: OpenAIResponsesCompat = field(default_factory=OpenAIResponsesCompat)
    metadata: dict[str, Any] = field(default_factory=dict)

    async def stream(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessageStream:
        return await OpenAIResponsesProvider.stream(self, model, context, options)

    async def complete(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessage:
        return await OpenAIResponsesProvider.complete(self, model, context, options)

    def _resolve_config(
        self, model: Model, options: AzureOpenAIResponsesOptions | None = None
    ) -> tuple[str, str]:
        api_version = (
            options.azure_api_version
            if options and options.azure_api_version
            else os.getenv("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION)
        )
        base_url = (
            (options.azure_base_url or "").strip() if options else ""
        ) or os.getenv("AZURE_OPENAI_BASE_URL", "").strip()
        resource_name = (
            options.azure_resource_name if options and options.azure_resource_name else os.getenv("AZURE_OPENAI_RESOURCE_NAME")
        )
        if not base_url and resource_name:
            base_url = f"https://{resource_name}.openai.azure.com/openai/v1"
        if not base_url:
            base_url = model.base_url or "https://example-resource.openai.azure.com/openai/v1"
        return base_url.rstrip("/"), api_version

    def _resolve_deployment_name(self, model: Model, options: AzureOpenAIResponsesOptions | None = None) -> str:
        if options and options.azure_deployment_name:
            return options.azure_deployment_name
        mapping = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME_MAP", "")
        for entry in mapping.split(","):
            if not entry.strip() or "=" not in entry:
                continue
            model_id, deployment = entry.split("=", 1)
            if model_id.strip() == model.id:
                return deployment.strip()
        return model.id

    def build_request(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> ProviderRequest:
        base_url, api_version = self._resolve_config(model, options if isinstance(options, AzureOpenAIResponsesOptions) else None)
        deployment_name = self._resolve_deployment_name(model, options if isinstance(options, AzureOpenAIResponsesOptions) else None)
        request = OpenAIResponsesProvider.build_request(self, model, context, options)
        request.url = f"{base_url}/deployments/{deployment_name}/responses?api-version={api_version}"
        request.headers.pop("authorization", None)
        api_key = getattr(options, "api_key", None) or os.getenv("AZURE_OPENAI_API_KEY")
        if api_key:
            request.headers["api-key"] = api_key
        return request
