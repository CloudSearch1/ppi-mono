"""Application-level skeleton for the pods runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .protocols import AgentCommandBridge, PodConfigStore, PodRuntime, SSHExecutor


@dataclass(slots=True)
class PodsAppConfig:
    config_dir: str


class PodsApp(Protocol):
    async def run(self, argv: list[str]) -> int: ...


@dataclass(slots=True)
class DefaultPodsApp:
    config: PodsAppConfig
    store: PodConfigStore
    remote: SSHExecutor
    runtime: PodRuntime
    agent: AgentCommandBridge

    async def run(self, argv: list[str]) -> int:
        # Command dispatch is intentionally left to the CLI layer.
        # This object exists so callers can wire dependencies in one place.
        return 0


def build_pods_app(
    config: PodsAppConfig,
    store: PodConfigStore,
    remote: SSHExecutor,
    runtime: PodRuntime,
    agent: AgentCommandBridge,
) -> DefaultPodsApp:
    return DefaultPodsApp(
        config=config,
        store=store,
        remote=remote,
        runtime=runtime,
        agent=agent,
    )
