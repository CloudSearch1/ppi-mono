"""Shared message, model, and request data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

ThinkingLevel: TypeAlias = Literal["minimal", "low", "medium", "high", "xhigh"]
CacheRetention: TypeAlias = Literal["none", "short", "long"]
Transport: TypeAlias = Literal["sse", "websocket", "auto"]
StopReason: TypeAlias = Literal["stop", "length", "toolUse", "error", "aborted"]
JsonValue: TypeAlias = dict[str, Any] | list[Any] | str | int | float | bool | None


@dataclass(slots=True)
class TextContent:
    type: Literal["text"] = "text"
    text: str = ""
    text_signature: str | None = None


@dataclass(slots=True)
class ThinkingContent:
    type: Literal["thinking"] = "thinking"
    thinking: str = ""
    thinking_signature: str | None = None
    redacted: bool = False


@dataclass(slots=True)
class ImageContent:
    type: Literal["image"] = "image"
    data: str = ""
    mime_type: str = "image/png"


@dataclass(slots=True)
class ToolCall:
    type: Literal["toolCall"] = "toolCall"
    id: str = ""
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    thought_signature: str | None = None


ContentBlock: TypeAlias = TextContent | ThinkingContent | ImageContent | ToolCall


@dataclass(slots=True)
class Usage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    total_tokens: int = 0
    cost: dict[str, float] = field(
        default_factory=lambda: {
            "input": 0.0,
            "output": 0.0,
            "cacheRead": 0.0,
            "cacheWrite": 0.0,
            "total": 0.0,
        }
    )


@dataclass(slots=True)
class UserMessage:
    role: Literal["user"] = "user"
    content: str | list[TextContent | ImageContent] = ""
    timestamp: int = 0


@dataclass(slots=True)
class AssistantMessage:
    role: Literal["assistant"] = "assistant"
    content: list[TextContent | ThinkingContent | ToolCall] = field(default_factory=list)
    api: str = ""
    provider: str = ""
    model: str = ""
    response_id: str | None = None
    usage: Usage = field(default_factory=Usage)
    stop_reason: StopReason = "stop"
    error_message: str | None = None
    timestamp: int = 0


@dataclass(slots=True)
class ToolResultMessage:
    role: Literal["toolResult"] = "toolResult"
    tool_call_id: str = ""
    tool_name: str = ""
    content: list[TextContent | ImageContent] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    is_error: bool = False
    timestamp: int = 0


Message: TypeAlias = UserMessage | AssistantMessage | ToolResultMessage


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Context:
    system_prompt: str | None = None
    messages: list[Message] = field(default_factory=list)
    tools: list[Tool] = field(default_factory=list)


@dataclass(slots=True)
class StreamOptions:
    temperature: float | None = None
    max_tokens: int | None = None
    signal: Any | None = None
    api_key: str | None = None
    transport: Transport = "sse"
    cache_retention: CacheRetention = "short"
    session_id: str | None = None
    on_payload: Any | None = None
    headers: dict[str, str] = field(default_factory=dict)
    max_retry_delay_ms: int = 60_000
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SimpleStreamOptions(StreamOptions):
    reasoning: ThinkingLevel | None = None
    thinking_budgets: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class OpenAICompletionsCompat:
    supports_store: bool | None = None
    supports_developer_role: bool | None = None
    supports_reasoning_effort: bool | None = None
    supports_usage_in_streaming: bool | None = None
    supports_strict_mode: bool | None = None
    max_tokens_field: Literal["max_completion_tokens", "max_tokens"] | None = None
    requires_tool_result_name: bool | None = None
    requires_assistant_after_tool_result: bool | None = None
    requires_thinking_as_text: bool | None = None
    thinking_format: Literal["openai", "zai", "qwen"] | None = None


@dataclass(slots=True)
class OpenAIResponsesCompat:
    pass


@dataclass(slots=True)
class OpenRouterRouting:
    provider_order: list[str] = field(default_factory=list)
    ignore_fallbacks: bool = False


@dataclass(slots=True)
class VercelGatewayRouting:
    provider_order: list[str] = field(default_factory=list)
    region: str | None = None


@dataclass(slots=True)
class ProviderRef:
    provider: str
    model_id: str


@dataclass(slots=True)
class Model:
    provider: str
    api: str
    id: str
    name: str | None = None
    base_url: str | None = None
    reasoning: bool = False
    input: list[str] = field(default_factory=list)
    output: list[str] = field(default_factory=list)
    context_window: int | None = None
    max_output_tokens: int | None = None
    compat: OpenAICompletionsCompat | OpenAIResponsesCompat | None = None
