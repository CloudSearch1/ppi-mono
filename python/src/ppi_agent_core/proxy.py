"""Proxy transport skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ppi_ai import Context, Model, SimpleStreamOptions

from .types import StreamFn


@dataclass(slots=True)
class ProxyStreamOptions(SimpleStreamOptions):
    proxy_url: str | None = None
    auth_token: str | None = None


async def stream_proxy(
    model: Model, context: Context, options: ProxyStreamOptions | None = None
) -> Any:
    raise NotImplementedError
