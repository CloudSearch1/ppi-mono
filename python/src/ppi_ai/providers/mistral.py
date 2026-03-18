"""Mistral provider adapter template."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import AssistantMessage, Context, Model, OpenAICompletionsCompat, StreamOptions
from ..registry import AssistantMessageStream
from .openai_completions import OpenAICompletionsProvider
from .common import ProviderRequest


@dataclass(slots=True)
class MistralProvider(OpenAICompletionsProvider):
    name: str = "mistral"
    api: str = "mistral-conversations"
    compat: OpenAICompletionsCompat = field(default_factory=OpenAICompletionsCompat)
    metadata: dict[str, Any] = field(default_factory=dict)

    async def stream(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessageStream:
        return await OpenAICompletionsProvider.stream(self, model, context, options)

    async def complete(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessage:
        return await OpenAICompletionsProvider.complete(self, model, context, options)

    def build_request(self, model: Model, context: Context, options: StreamOptions | None = None) -> ProviderRequest:
        request = OpenAICompletionsProvider.build_request(self, model, context, options)
        base_url = model.base_url or "https://api.mistral.ai/v1"
        request.url = f"{base_url.rstrip('/')}/chat/completions"
        return request
