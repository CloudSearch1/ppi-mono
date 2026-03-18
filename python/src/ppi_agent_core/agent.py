"""Agent state machine skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ppi_ai import Model

from .events import AgentEvent
from .types import (
    AgentContext,
    AgentMessage,
    AgentState,
    AgentTool,
    AfterToolCallContext,
    AfterToolCallResult,
    BeforeToolCallContext,
    BeforeToolCallResult,
    StreamFn,
    ThinkingLevel,
    ToolExecutionMode,
)


@dataclass(slots=True)
class AgentOptions:
    initial_state: AgentState | None = None
    convert_to_llm: Callable[[list[AgentMessage]], list[Any]] | None = None
    transform_context: Callable[[list[AgentMessage], Any | None], Any] | None = None
    steering_mode: str = "one-at-a-time"
    follow_up_mode: str = "one-at-a-time"
    stream_fn: StreamFn | None = None
    session_id: str | None = None
    get_api_key: Callable[[str], Any] | None = None
    on_payload: Any | None = None
    thinking_budgets: dict[str, int] | None = None
    transport: str = "sse"
    max_retry_delay_ms: int | None = None
    tool_execution: ToolExecutionMode = "parallel"
    before_tool_call: Callable[[BeforeToolCallContext, Any | None], Any] | None = None
    after_tool_call: Callable[[AfterToolCallContext, Any | None], Any] | None = None


class Agent:
    def __init__(self, options: AgentOptions | None = None) -> None:
        self.options = options or AgentOptions()
        self.state = self.options.initial_state or AgentState()
        self._listeners: list[Callable[[AgentEvent], None]] = []
        self.stream_fn = self.options.stream_fn

    async def prompt(self, message: AgentMessage | str) -> None:
        raise NotImplementedError

    async def continue_(self) -> None:
        raise NotImplementedError

    def abort(self) -> None:
        raise NotImplementedError

    def subscribe(self, callback: Callable[[AgentEvent], None]) -> Callable[[], None]:
        self._listeners.append(callback)

        def unsubscribe() -> None:
            self._listeners.remove(callback)

        return unsubscribe

    def set_tools(self, tools: list[AgentTool]) -> None:
        self.state.tools = tools

    def set_model(self, model: Model) -> None:
        self.state.model = model

    def set_thinking_level(self, thinking_level: ThinkingLevel) -> None:
        self.state.thinking_level = thinking_level
