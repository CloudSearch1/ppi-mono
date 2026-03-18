"""Core agent runtime types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Protocol, TypeAlias

from ppi_ai import Context, Message, Model, SimpleStreamOptions, Tool, ToolCall, Usage

ThinkingLevel: TypeAlias = Literal["off", "minimal", "low", "medium", "high", "xhigh"]
ToolExecutionMode: TypeAlias = Literal["parallel", "sequential"]


@dataclass(slots=True)
class CustomAgentMessage:
    role: str
    timestamp: int = 0
    payload: dict[str, Any] = field(default_factory=dict)


AgentMessage: TypeAlias = Message | CustomAgentMessage
AgentToolCall: TypeAlias = ToolCall


@dataclass(slots=True)
class AgentToolResult:
    content: list[Any] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


AgentToolUpdateCallback: TypeAlias = Callable[[AgentToolResult], None]


@dataclass(slots=True)
class BeforeToolCallContext:
    assistant_message: Any
    tool_call: Any
    args: Any
    context: Any


@dataclass(slots=True)
class BeforeToolCallResult:
    block: bool = False
    reason: str | None = None


@dataclass(slots=True)
class AfterToolCallContext:
    assistant_message: Any
    tool_call: Any
    args: Any
    result: AgentToolResult
    is_error: bool
    context: Any


@dataclass(slots=True)
class AfterToolCallResult:
    content: list[Any] | None = None
    details: dict[str, Any] | None = None
    is_error: bool | None = None


class AgentTool(Protocol):
    name: str
    description: str
    parameters: Any

    async def execute(
        self,
        tool_call_id: str,
        args: Any,
        signal: Any | None = None,
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        ...


@dataclass(slots=True)
class AgentContext:
    system_prompt: str | None = None
    messages: list[AgentMessage] = field(default_factory=list)
    tools: list[AgentTool] = field(default_factory=list)


@dataclass(slots=True)
class AgentState:
    system_prompt: str = ""
    model: Model | None = None
    thinking_level: ThinkingLevel = "off"
    tools: list[AgentTool] = field(default_factory=list)
    messages: list[AgentMessage] = field(default_factory=list)
    is_streaming: bool = False
    stream_message: AgentMessage | None = None
    pending_tool_calls: set[str] = field(default_factory=set)
    error: str | None = None


@dataclass(slots=True)
class AgentLoopConfig(SimpleStreamOptions):
    model: Model | None = None
    convert_to_llm: Callable[[list[AgentMessage]], list[Message]] | None = None
    transform_context: Callable[[list[AgentMessage], Any | None], Any] | None = None
    tool_execution: ToolExecutionMode = "parallel"
    get_steering_messages: Callable[[], Any] | None = None
    get_follow_up_messages: Callable[[], Any] | None = None
    before_tool_call: Callable[[BeforeToolCallContext, Any | None], Any] | None = None
    after_tool_call: Callable[[AfterToolCallContext, Any | None], Any] | None = None


StreamFn: TypeAlias = Callable[[Model, Context, SimpleStreamOptions | None], Any]
