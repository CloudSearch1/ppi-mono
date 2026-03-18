"""Agent runtime events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from .types import AgentMessage, AgentToolResult


@dataclass(slots=True)
class AgentStartEvent:
    type: Literal["agent_start"] = "agent_start"


@dataclass(slots=True)
class AgentEndEvent:
    type: Literal["agent_end"] = "agent_end"
    messages: list[AgentMessage] = field(default_factory=list)


@dataclass(slots=True)
class TurnStartEvent:
    type: Literal["turn_start"] = "turn_start"


@dataclass(slots=True)
class TurnEndEvent:
    type: Literal["turn_end"] = "turn_end"
    message: Any | None = None
    tool_results: list[AgentToolResult] = field(default_factory=list)


@dataclass(slots=True)
class MessageStartEvent:
    type: Literal["message_start"] = "message_start"
    message: AgentMessage | None = None


@dataclass(slots=True)
class MessageUpdateEvent:
    type: Literal["message_update"] = "message_update"
    assistant_message_event: Any | None = None
    message: AgentMessage | None = None


@dataclass(slots=True)
class MessageEndEvent:
    type: Literal["message_end"] = "message_end"
    message: AgentMessage | None = None


@dataclass(slots=True)
class ToolExecutionStartEvent:
    type: Literal["tool_execution_start"] = "tool_execution_start"
    tool_call_id: str = ""
    tool_name: str = ""
    args: Any = None


@dataclass(slots=True)
class ToolExecutionUpdateEvent:
    type: Literal["tool_execution_update"] = "tool_execution_update"
    tool_call_id: str = ""
    tool_name: str = ""
    args: Any = None
    partial_result: AgentToolResult | None = None


@dataclass(slots=True)
class ToolExecutionEndEvent:
    type: Literal["tool_execution_end"] = "tool_execution_end"
    tool_call_id: str = ""
    tool_name: str = ""
    result: AgentToolResult | None = None
    is_error: bool = False


AgentEvent: TypeAlias = (
    AgentStartEvent
    | AgentEndEvent
    | TurnStartEvent
    | TurnEndEvent
    | MessageStartEvent
    | MessageUpdateEvent
    | MessageEndEvent
    | ToolExecutionStartEvent
    | ToolExecutionUpdateEvent
    | ToolExecutionEndEvent
)


EventSubscriber: TypeAlias = Any
