"""Agent loop entry points."""

from __future__ import annotations

from typing import Any

from .events import AgentEvent
from .types import AgentContext, AgentMessage, AgentLoopConfig, StreamFn


async def run_agent_loop(
    prompts: list[AgentMessage],
    context: AgentContext,
    config: AgentLoopConfig,
    emit: Any,
    signal: Any | None = None,
    stream_fn: StreamFn | None = None,
) -> list[AgentMessage]:
    raise NotImplementedError


async def run_agent_loop_continue(
    context: AgentContext,
    config: AgentLoopConfig,
    emit: Any,
    signal: Any | None = None,
    stream_fn: StreamFn | None = None,
) -> list[AgentMessage]:
    raise NotImplementedError
