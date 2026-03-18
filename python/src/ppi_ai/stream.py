"""High-level streaming helpers."""

from __future__ import annotations

from .models import AssistantMessage, Context, Model, SimpleStreamOptions
from .registry import AssistantMessageStream, get_provider


async def stream(
    model: Model, context: Context, options: SimpleStreamOptions | None = None
) -> AssistantMessageStream:
    """Look up the provider for ``model.provider`` and start a stream."""
    provider = get_provider(model.provider)
    return await provider.stream(model, context, options)


async def complete(
    model: Model, context: Context, options: SimpleStreamOptions | None = None
) -> AssistantMessage:
    """Look up the provider for ``model.provider`` and run a one-shot completion."""
    provider = get_provider(model.provider)
    return await provider.complete(model, context, options)
