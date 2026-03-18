"""Base provider adapter contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import AssistantMessage, Context, Model, StreamOptions
from ..registry import AssistantMessageStream, Provider
from .common import (
    ProviderAssistantMessageStream,
    HttpxProviderClient,
    ProviderHttpClient,
    ProviderRequest,
    StreamChunk,
    StreamParseState,
    finalize_state,
)


@dataclass(slots=True)
class BaseProvider(Provider):
    """Shared base class for provider adapters."""

    name: str = ""
    api: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    client: ProviderHttpClient | None = None

    async def stream(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessageStream:
        normalized = self.normalize_options(options)
        request = self.build_request(model, context, normalized)
        if self.client is None:
            self.client = HttpxProviderClient(timeout=normalized.max_retry_delay_ms / 1000 if normalized.max_retry_delay_ms else None)
        return ProviderAssistantMessageStream(provider=self, client=self.client, request=request)

    async def complete(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessage:
        stream = await self.stream(model, context, options)
        return await stream.result()

    def supports_model(self, model: Model) -> bool:
        return model.provider == self.name or model.api == self.api

    def normalize_options(self, options: StreamOptions | None) -> StreamOptions:
        return options or StreamOptions()

    def build_request(self, model: Model, context: Context, options: StreamOptions | None = None) -> ProviderRequest:
        raise NotImplementedError

    def create_parse_state(self) -> StreamParseState:
        return StreamParseState()

    def parse_chunk(self, chunk: StreamChunk, state: StreamParseState) -> None:
        raise NotImplementedError

    def finalize_message(self, state: StreamParseState) -> AssistantMessage:
        return finalize_state(state)

    def finalize(self, state: StreamParseState) -> AssistantMessage:
        return self.finalize_message(state)
