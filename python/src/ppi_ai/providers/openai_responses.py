"""OpenAI Responses provider adapter template."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..models import (
    AssistantMessage,
    Context,
    Model,
    OpenAIResponsesCompat,
    StreamOptions,
    TextContent,
    ThinkingContent,
    ToolCall,
)
from ..events import ThinkingStartEvent
from ..registry import AssistantMessageStream
from .base import BaseProvider
from .common import ProviderRequest, StreamChunk, StreamParseState, apply_text_delta, apply_thinking_delta


@dataclass(slots=True)
class OpenAIResponsesProvider(BaseProvider):
    name: str = "openai"
    api: str = "openai-responses"
    compat: OpenAIResponsesCompat = field(default_factory=OpenAIResponsesCompat)
    metadata: dict[str, Any] = field(default_factory=dict)

    async def stream(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessageStream:
        """Start a streaming OpenAI Responses request."""
        return await BaseProvider.stream(self, model, context, options)

    async def complete(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessage:
        """Run a one-shot OpenAI Responses request."""
        return await BaseProvider.complete(self, model, context, options)

    def to_payload(self, context: Context) -> dict[str, Any]:
        """Convert shared context into a Responses API payload."""
        input_items: list[dict[str, Any]] = []
        if context.system_prompt:
            input_items.append({"role": "system", "content": context.system_prompt})

        for message in context.messages:
            if message.role == "user":
                content = message.content
                if isinstance(content, str):
                    input_items.append({"role": "user", "content": content})
                else:
                    content_parts: list[dict[str, Any]] = []
                    for block in content:
                        block_type = getattr(block, "type", None)
                        if block_type == "text":
                            content_parts.append({"type": "input_text", "text": getattr(block, "text", "")})
                        elif block_type == "image":
                            content_parts.append(
                                {
                                    "type": "input_image",
                                    "image_url": f"data:{getattr(block, 'mime_type', 'image/png')};base64,{getattr(block, 'data', '')}",
                                }
                            )
                    input_items.append({"role": "user", "content": content_parts})
            elif message.role == "assistant":
                content_parts: list[dict[str, Any]] = []
                for block in message.content:
                    if isinstance(block, TextContent):
                        content_parts.append({"type": "output_text", "text": block.text})
                    elif isinstance(block, ThinkingContent):
                        content_parts.append({"type": "reasoning", "thinking": block.thinking})
                    elif isinstance(block, ToolCall):
                        content_parts.append(
                            {
                                "type": "function_call",
                                "call_id": block.id,
                                "name": block.name,
                                "arguments": json.dumps(block.arguments, ensure_ascii=False),
                            }
                        )
                input_items.append({"role": "assistant", "content": content_parts})
            elif message.role == "toolResult":
                input_items.append(
                    {
                        "role": "tool",
                        "tool_call_id": getattr(message, "tool_call_id", ""),
                        "name": getattr(message, "tool_name", ""),
                        "content": "".join(getattr(block, "text", "") for block in getattr(message, "content", [])),
                    }
                )

        return {"input": input_items}

    def build_request(self, model: Model, context: Context, options: StreamOptions | None = None) -> ProviderRequest:
        options = self.normalize_options(options)
        base_url = model.base_url or "https://api.openai.com/v1"
        payload = self.to_payload(context)
        payload.update(
            {
                "model": model.id,
                "stream": True,
            }
        )
        if options.max_tokens is not None:
            payload["max_output_tokens"] = options.max_tokens
        elif model.max_output_tokens is not None:
            payload["max_output_tokens"] = model.max_output_tokens
        if options.temperature is not None:
            payload["temperature"] = options.temperature
        if context.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
                for tool in context.tools
            ]
        headers = {"content-type": "application/json", **(options.headers or {})}
        if options.api_key:
            headers["authorization"] = f"Bearer {options.api_key}"
        return ProviderRequest(
            url=f"{base_url.rstrip('/')}/responses",
            headers=headers,
            json=payload,
            stream=True,
            timeout=getattr(options, "timeout", None),
            metadata={"provider": "openai", "api": self.api},
        )

    def parse_chunk(self, chunk: StreamChunk, state: StreamParseState) -> None:
        data = chunk.data or {}
        event_type = chunk.event or data.get("type")

        if chunk.raw.strip() == "[DONE]":
            state.set_stop_reason("stop")
            return
        if "error" in data:
            error = data.get("error")
            state.set_error(error.get("message") if isinstance(error, dict) else str(error))
            state.set_stop_reason("error")
            return

        response = data.get("response") or {}
        if response.get("id"):
            state.set_response_id(response["id"])
        if response.get("usage"):
            state.set_usage(response["usage"])

        if event_type in {"response.output_text.delta", "output_text.delta"}:
            delta = data.get("delta") or data.get("text") or ""
            apply_text_delta(state, delta, int(data.get("index", 0)))
            return

        if event_type in {"response.reasoning.delta", "reasoning.delta"}:
            delta = data.get("delta") or data.get("thinking") or ""
            apply_thinking_delta(state, delta, int(data.get("index", 0)))
            return

        if event_type in {"response.function_call_arguments.delta", "function_call_arguments.delta"}:
            index = int(data.get("index", 0))
            call = state.emit_tool_call_start(index)
            item = data.get("item") or {}
            if item.get("call_id"):
                call.id = item["call_id"]
            if item.get("name"):
                call.name = item["name"]
            delta = data.get("delta") or data.get("arguments") or ""
            if delta:
                state.append_tool_call_delta(index, delta)
            return

        if event_type in {"response.function_call_arguments.done", "function_call_arguments.done"}:
            index = int(data.get("index", 0))
            call = state.emit_tool_call_start(index)
            arguments = data.get("arguments") or ""
            if arguments:
                call.arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
            return

        if event_type in {"response.output_item.added", "output_item.added"}:
            item = data.get("item") or {}
            index = int(data.get("index", 0))
            if item.get("type") == "reasoning":
                if index not in state.thinking_started_indices:
                    state.thinking_started_indices.add(index)
                    state.emit(ThinkingStartEvent(content_index=index, partial=state.build_message()))
            elif item.get("type") == "function_call":
                call = state.emit_tool_call_start(index)
                call.id = item.get("call_id", call.id)
                call.name = item.get("name", call.name)
            elif item.get("type") == "message":
                state.assistant_message.provider = self.name
                state.assistant_message.api = self.api
            return

        if event_type in {"response.output_item.done", "output_item.done"}:
            item = data.get("item") or {}
            index = int(data.get("index", 0))
            if item.get("type") == "reasoning":
                summary = item.get("summary") or []
                if summary:
                    content = "\n\n".join(part.get("text", "") for part in summary if isinstance(part, dict))
                    if content:
                        state.emit_thinking_delta(index, content)
            elif item.get("type") == "function_call":
                call = state.emit_tool_call_start(index)
                call.id = item.get("call_id", call.id)
                call.name = item.get("name", call.name)
                if item.get("arguments"):
                    if isinstance(item["arguments"], str):
                        try:
                            call.arguments = json.loads(item["arguments"])
                        except json.JSONDecodeError:
                            call.arguments = {}
                    else:
                        call.arguments = item["arguments"]
                state.emit_tool_call_end(index, call)
            elif item.get("type") == "message":
                output = item.get("content") or []
                text = "".join(part.get("text", "") for part in output if isinstance(part, dict))
                if text:
                    state.emit_text_delta(index, text)
            return

        if event_type in {"response.completed", "completed"}:
            if response.get("usage"):
                state.set_usage(response["usage"])
            state.set_stop_reason("stop")
            return

        if event_type in {"response.failed", "response.error"}:
            error = data.get("error") or response.get("error")
            state.set_error(error.get("message") if isinstance(error, dict) else str(error))
            state.set_stop_reason("error")
