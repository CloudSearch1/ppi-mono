"""Streaming events emitted by provider adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .models import AssistantMessage, ToolCall


@dataclass(slots=True)
class StreamStartEvent:
    type: Literal["start"] = "start"
    partial: AssistantMessage | None = None


@dataclass(slots=True)
class TextStartEvent:
    type: Literal["text_start"] = "text_start"
    content_index: int = 0
    partial: AssistantMessage | None = None


@dataclass(slots=True)
class TextDeltaEvent:
    type: Literal["text_delta"] = "text_delta"
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage | None = None


@dataclass(slots=True)
class TextEndEvent:
    type: Literal["text_end"] = "text_end"
    content_index: int = 0
    content: str = ""
    partial: AssistantMessage | None = None


@dataclass(slots=True)
class ThinkingStartEvent:
    type: Literal["thinking_start"] = "thinking_start"
    content_index: int = 0
    partial: AssistantMessage | None = None


@dataclass(slots=True)
class ThinkingDeltaEvent:
    type: Literal["thinking_delta"] = "thinking_delta"
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage | None = None


@dataclass(slots=True)
class ThinkingEndEvent:
    type: Literal["thinking_end"] = "thinking_end"
    content_index: int = 0
    content: str = ""
    partial: AssistantMessage | None = None


@dataclass(slots=True)
class ToolCallStartEvent:
    type: Literal["toolcall_start"] = "toolcall_start"
    content_index: int = 0
    partial: AssistantMessage | None = None


@dataclass(slots=True)
class ToolCallDeltaEvent:
    type: Literal["toolcall_delta"] = "toolcall_delta"
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage | None = None


@dataclass(slots=True)
class ToolCallEndEvent:
    type: Literal["toolcall_end"] = "toolcall_end"
    content_index: int = 0
    tool_call: ToolCall | None = None
    partial: AssistantMessage | None = None


@dataclass(slots=True)
class StreamDoneEvent:
    type: Literal["done"] = "done"
    reason: Literal["stop", "length", "toolUse"] = "stop"
    message: AssistantMessage | None = None


@dataclass(slots=True)
class StreamErrorEvent:
    type: Literal["error"] = "error"
    reason: Literal["aborted", "error"] = "error"
    error: AssistantMessage | None = None


AssistantMessageEvent: TypeAlias = (
    StreamStartEvent
    | TextStartEvent
    | TextDeltaEvent
    | TextEndEvent
    | ThinkingStartEvent
    | ThinkingDeltaEvent
    | ThinkingEndEvent
    | ToolCallStartEvent
    | ToolCallDeltaEvent
    | ToolCallEndEvent
    | StreamDoneEvent
    | StreamErrorEvent
)
