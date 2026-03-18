"""Shared provider parsing templates."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from ..events import (
    AssistantMessageEvent,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamStartEvent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)
from ..models import (
    AssistantMessage,
    AssistantMessage as AssistantMessageModel,
    Context,
    Model,
    StreamOptions,
    TextContent,
    ThinkingContent,
    ToolCall,
    Usage,
)


@dataclass(slots=True)
class ProviderRequest:
    method: str = "POST"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    json: dict[str, Any] = field(default_factory=dict)
    stream: bool = True
    timeout: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderResponse:
    status: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = None
    request_id: str | None = None


@dataclass(slots=True)
class StreamChunk:
    raw: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    event: str | None = None


@dataclass(slots=True)
class StreamParseState:
    text_parts: list[str] = field(default_factory=list)
    thinking_parts: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_arguments: dict[int, str] = field(default_factory=dict)
    active_tool_call_index: int | None = None
    assistant_message: AssistantMessageModel = field(default_factory=AssistantMessageModel)
    events: list[AssistantMessageEvent] = field(default_factory=list)
    started: bool = False
    finished: bool = False
    text_started_indices: set[int] = field(default_factory=set)
    thinking_started_indices: set[int] = field(default_factory=set)
    tool_call_started_indices: set[int] = field(default_factory=set)

    def emit(self, event: AssistantMessageEvent) -> None:
        self.events.append(event)

    def start_stream(self) -> None:
        if self.started:
            return
        self.started = True
        self.emit(StreamStartEvent(partial=self.build_message()))

    def add_text(self, text: str) -> None:
        if not text:
            return
        self.text_parts.append(text)
        self.assistant_message.content.append(TextContent(text=text))

    def add_thinking(self, thinking: str) -> None:
        if not thinking:
            return
        self.thinking_parts.append(thinking)
        self.assistant_message.content.append(ThinkingContent(thinking=thinking))

    def add_tool_call(self, tool_call: ToolCall) -> None:
        self.tool_calls.append(tool_call)
        self.assistant_message.content.append(tool_call)

    def emit_text_delta(self, index: int, delta: str) -> None:
        if not delta:
            return
        if index not in self.text_started_indices:
            self.text_started_indices.add(index)
            self.emit(TextStartEvent(content_index=index, partial=self.build_message()))
        self.add_text(delta)
        self.emit(TextDeltaEvent(content_index=index, delta=delta, partial=self.build_message()))

    def emit_thinking_delta(self, index: int, delta: str) -> None:
        if not delta:
            return
        if index not in self.thinking_started_indices:
            self.thinking_started_indices.add(index)
            self.emit(ThinkingStartEvent(content_index=index, partial=self.build_message()))
        self.add_thinking(delta)
        self.emit(ThinkingDeltaEvent(content_index=index, delta=delta, partial=self.build_message()))

    def emit_tool_call_start(self, index: int, tool_call: ToolCall | None = None) -> ToolCall:
        if index not in self.tool_call_started_indices:
            self.tool_call_started_indices.add(index)
            self.emit(ToolCallStartEvent(content_index=index, partial=self.build_message()))
        if tool_call is None:
            while len(self.tool_calls) <= index:
                self.tool_calls.append(ToolCall())
            tool_call = self.tool_calls[index]
        else:
            while len(self.tool_calls) <= index:
                self.tool_calls.append(ToolCall())
            self.tool_calls[index] = tool_call
            self._sync_assistant_tool_call(index, tool_call)
        return tool_call

    def append_tool_call_delta(self, index: int, delta: str) -> ToolCall:
        current = self.emit_tool_call_start(index)
        self.tool_call_arguments[index] = self.tool_call_arguments.get(index, "") + delta
        current.arguments = _safe_json_object(self.tool_call_arguments[index])
        self.tool_calls[index] = current
        self._sync_assistant_tool_call(index, current)
        self.emit(ToolCallDeltaEvent(content_index=index, delta=delta, partial=self.build_message()))
        return current

    def emit_tool_call_end(self, index: int, tool_call: ToolCall | None = None) -> None:
        if tool_call is None and index < len(self.tool_calls):
            tool_call = self.tool_calls[index]
        if tool_call is None:
            return
        self._sync_assistant_tool_call(index, tool_call)
        self.emit(ToolCallEndEvent(content_index=index, tool_call=tool_call, partial=self.build_message()))

    def _sync_assistant_tool_call(self, index: int, tool_call: ToolCall) -> None:
        while len(self.assistant_message.content) <= index:
            self.assistant_message.content.append(ToolCall())
        self.assistant_message.content[index] = tool_call

    def build_message(self) -> AssistantMessageModel:
        if self.text_parts and not any(isinstance(block, TextContent) for block in self.assistant_message.content):
            self.assistant_message.content.extend(TextContent(text=text) for text in self.text_parts)
        if self.thinking_parts and not any(isinstance(block, ThinkingContent) for block in self.assistant_message.content):
            self.assistant_message.content.extend(ThinkingContent(thinking=thinking) for thinking in self.thinking_parts)
        if self.tool_calls:
            for index, tool_call in enumerate(self.tool_calls):
                self._sync_assistant_tool_call(index, tool_call)
        return self.assistant_message

    def set_usage(self, usage: dict[str, Any] | Usage | None) -> None:
        if usage is None:
            return
        if isinstance(usage, Usage):
            self.assistant_message.usage = usage
            return
        if isinstance(usage, dict):
            current = self.assistant_message.usage
            current.input = int(
                usage.get(
                    "input_tokens",
                    usage.get("inputTokens", usage.get("input", current.input)),
                )
            )
            current.output = int(
                usage.get(
                    "output_tokens",
                    usage.get("outputTokens", usage.get("output", current.output)),
                )
            )
            current.cache_read = int(
                usage.get(
                    "cache_read",
                    usage.get("cacheRead", usage.get("cache_read_tokens", current.cache_read)),
                )
            )
            current.cache_write = int(
                usage.get(
                    "cache_write",
                    usage.get("cacheWrite", usage.get("cache_write_tokens", current.cache_write)),
                )
            )
            current.total_tokens = int(
                usage.get("total_tokens", usage.get("totalTokens", current.total_tokens))
            )

    def set_stop_reason(self, reason: str | None) -> None:
        if reason:
            self.assistant_message.stop_reason = reason

    def set_response_id(self, response_id: str | None) -> None:
        if response_id:
            self.assistant_message.response_id = response_id

    def set_error(self, error_message: str | None) -> None:
        self.assistant_message.error_message = error_message

    def finalize_events(self) -> None:
        if self.finished:
            return
        self.finished = True
        for index in sorted(self.text_started_indices):
            self.emit(TextEndEvent(content_index=index, content="".join(self.text_parts), partial=self.build_message()))
        for index in sorted(self.thinking_started_indices):
            self.emit(
                ThinkingEndEvent(
                    content_index=index,
                    content="".join(self.thinking_parts),
                    partial=self.build_message(),
                )
            )
        for index in sorted(self.tool_call_started_indices):
            tool_call = self.tool_calls[index] if index < len(self.tool_calls) else None
            if tool_call is not None:
                self.emit_tool_call_end(index, tool_call)

    def consume_events(self, start_index: int) -> list[AssistantMessageEvent]:
        return self.events[start_index:]


def _safe_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {"value": value}


def parse_sse_chunk(raw: str) -> StreamChunk:
    event: str | None = None
    data_lines: list[str] = []
    for line in raw.splitlines():
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].lstrip())
    data_text = "\n".join(data_lines).strip()
    try:
        data = json.loads(data_text) if data_text else {}
    except json.JSONDecodeError:
        data = {"text": data_text}
    return StreamChunk(raw=raw, event=event, data=data if isinstance(data, dict) else {"value": data})


def coerce_chunk(item: Any) -> StreamChunk:
    if isinstance(item, StreamChunk):
        return item
    if isinstance(item, bytes):
        return parse_sse_chunk(item.decode("utf-8", errors="ignore"))
    if isinstance(item, str):
        return parse_sse_chunk(item)
    if isinstance(item, dict):
        return StreamChunk(raw=json.dumps(item), data=item, event=item.get("event"))
    return StreamChunk(raw=str(item), data={"value": item})


def merge_usage(target: Usage, usage: dict[str, Any]) -> Usage:
    target.input = int(usage.get("input_tokens", usage.get("inputTokens", usage.get("input", target.input))))
    target.output = int(usage.get("output_tokens", usage.get("outputTokens", usage.get("output", target.output))))
    target.cache_read = int(
        usage.get("cache_read", usage.get("cacheRead", usage.get("cache_read_tokens", target.cache_read)))
    )
    target.cache_write = int(
        usage.get("cache_write", usage.get("cacheWrite", usage.get("cache_write_tokens", target.cache_write)))
    )
    target.total_tokens = int(usage.get("total_tokens", usage.get("totalTokens", target.total_tokens)))
    return target


def apply_text_delta(state: StreamParseState, delta: str, index: int = 0) -> None:
    state.emit_text_delta(index, delta)


def apply_thinking_delta(state: StreamParseState, delta: str, index: int = 0) -> None:
    state.emit_thinking_delta(index, delta)


def apply_tool_call_delta(state: StreamParseState, index: int, delta: str) -> ToolCall:
    return state.append_tool_call_delta(index, delta)


def finalize_state(state: StreamParseState) -> AssistantMessageModel:
    state.finalize_events()
    message = state.build_message()
    if not message.content and state.text_parts:
        message.content = [TextContent(text="".join(state.text_parts))]
    return message


class ProviderHttpClient(Protocol):
    async def request(self, request: ProviderRequest) -> ProviderResponse:
        ...

    async def stream(self, request: ProviderRequest) -> Any:
        ...


class ProviderParser(Protocol):
    def build_request(self, model: Model, context: Context, options: StreamOptions | None = None) -> ProviderRequest:
        ...

    def parse_chunk(self, chunk: StreamChunk, state: StreamParseState) -> None:
        ...

    def finalize(self, state: StreamParseState) -> AssistantMessageModel:
        ...


@dataclass(slots=True)
class HttpxProviderClient:
    client: httpx.AsyncClient | None = None
    timeout: float | None = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self.client is None:
            timeout = httpx.Timeout(self.timeout) if self.timeout is not None else httpx.Timeout(60.0)
            self.client = httpx.AsyncClient(timeout=timeout)
        return self.client

    async def request(self, request: ProviderRequest) -> ProviderResponse:
        client = self._ensure_client()
        response = await client.request(
            request.method,
            request.url,
            headers=request.headers,
            json=request.json if request.json else None,
            content=request.metadata.get("content") if request.metadata else None,
            timeout=request.timeout,
        )
        body: Any
        try:
            body = response.json()
        except Exception:
            body = response.text
        return ProviderResponse(
            status=response.status_code,
            headers=dict(response.headers),
            body=body,
            request_id=response.headers.get("x-request-id") or response.headers.get("request-id"),
        )

    async def stream(self, request: ProviderRequest) -> Any:
        client = self._ensure_client()
        return client.stream(
            request.method,
            request.url,
            headers=request.headers,
            json=request.json if request.json else None,
            content=request.metadata.get("content") if request.metadata else None,
            timeout=request.timeout,
        )

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None


@dataclass(slots=True)
class ProviderAssistantMessageStream:
    provider: ProviderParser
    client: ProviderHttpClient
    request: ProviderRequest
    state: StreamParseState = field(default_factory=StreamParseState)
    _final_message: AssistantMessageModel | None = None
    _cancelled: bool = False

    async def _iterate_source(self) -> Any:
        source = self.client.stream(self.request)
        if inspect.isawaitable(source):
            source = await source
        if hasattr(source, "__aenter__") and hasattr(source, "__aexit__"):
            async with source as stream:
                if hasattr(stream, "aiter_lines"):
                    async for item in stream.aiter_lines():
                        yield item
                elif hasattr(stream, "__aiter__"):
                    async for item in stream:
                        yield item
                else:
                    for item in stream:
                        yield item
            return
        if hasattr(source, "aiter_lines"):
            async for item in source.aiter_lines():
                yield item
            return
        if hasattr(source, "__aiter__"):
            async for item in source:
                yield item
            return
        for item in source:
            yield item

    async def _drain(self):
        self.state.start_stream()
        for event in self.state.consume_events(0):
            yield event
        try:
            async for item in self._iterate_source():
                if self._cancelled:
                    self.state.set_error("aborted")
                    break
                before = len(self.state.events)
                self.provider.parse_chunk(coerce_chunk(item), self.state)
                for event in self.state.consume_events(before):
                    yield event
            self.state.finalize_events()
            if self.state.assistant_message.error_message:
                yield StreamErrorEvent(
                    reason="aborted" if self.state.assistant_message.error_message == "aborted" else "error",
                    error=self.state.build_message(),
                )
            else:
                message = self.provider.finalize(self.state)
                self._final_message = message
                reason = message.stop_reason if message.stop_reason in {"stop", "length", "toolUse"} else "stop"
                yield StreamDoneEvent(reason=reason, message=message)
        except Exception as exc:
            self.state.set_error(str(exc))
            self.state.finalize_events()
            message = self.provider.finalize(self.state)
            self._final_message = message
            yield StreamErrorEvent(reason="error", error=message)

    def __aiter__(self):
        return self._drain()

    async def result(self) -> AssistantMessageModel:
        if self._final_message is not None:
            return self._final_message
        async for _ in self._drain():
            pass
        if self._final_message is None:
            self._final_message = self.provider.finalize(self.state)
        return self._final_message

    async def cancel(self) -> None:
        self._cancelled = True
