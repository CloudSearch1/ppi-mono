"""RPC protocol contracts."""

from __future__ import annotations

from .types import RpcCommand, RpcEnvelope, RpcResponse, RpcTransport


class RpcClient:
    def __init__(self, transport: RpcTransport | None = None) -> None:
        self.connected = False
        self.transport = transport

    def connect(self) -> None:
        if self.transport is None:
            raise RuntimeError("RpcClient requires a transport")
        self.transport.connect()
        self.connected = True

    def send(self, command: RpcCommand) -> RpcResponse:
        if self.transport is None:
            raise RuntimeError("RpcClient requires a transport")
        if not self.connected:
            self.connect()
        return self.transport.send(command)

    def close(self) -> None:
        if self.transport is not None:
            self.transport.close()
        self.connected = False
