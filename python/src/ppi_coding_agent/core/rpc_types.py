"""RPC protocol and dataclass definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class RpcCommand:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str | None = None


@dataclass(slots=True)
class RpcResponse:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str | None = None
    error: str | None = None


@dataclass(slots=True)
class RpcEnvelope:
    command: RpcCommand | None = None
    response: RpcResponse | None = None


class RpcTransport(Protocol):
    def connect(self) -> None:
        ...

    def close(self) -> None:
        ...

    def send(self, command: RpcCommand) -> RpcResponse:
        ...


__all__ = ["RpcCommand", "RpcEnvelope", "RpcResponse", "RpcTransport"]
