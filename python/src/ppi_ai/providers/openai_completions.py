"""OpenAI Completions provider adapter template."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..models import (
    AssistantMessage,
    Context,
    Model,
    OpenAICompletionsCompat,
    StreamOptions,
    TextContent,
    ThinkingContent,
    ToolCall,
    ToolResultMessage,
)
from ..registry import AssistantMessageStream
from .base import BaseProvider
from .common import ProviderRequest, StreamChunk, StreamParseState, apply_text_delta, apply_thinking_delta


def _join_text_content(parts: Any) -> str:
    if isinstance(parts, str):
        return parts
    if not parts:
        return ""
    return "".join(getattr(block, "text", "") for block in parts if getattr(block, "type", None) == "text")


@dataclass(slots=True)
class OpenAICompletionsProvider(BaseProvider):
    name: str = "openai"
    api: str = "openai-completions"
    compat: OpenAICompletionsCompat = field(default_factory=OpenAICompletionsCompat)
    metadata: dict[str, Any] = field(default_factory=dict)

    async def stream(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessageStream:
        """Start a streaming OpenAI Completions request."""
        return await BaseProvider.stream(self, model, context, options)

    async def complete(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessage:
        """Run a one-shot OpenAI Completions request."""
        return await BaseProvider.complete(self, model, context, options)

    def to_payload(self, context: Context) -> dict[str, Any]:
        """Convert shared context into an OpenAI-style payload."""
        messages: list[dict[str, Any]] = []
        if context.system_prompt:
            messages.append({"role": "system", "content": context.system_prompt})

        for message in context.messages:
            if message.role == "user":
                content = message.content
                if isinstance(content, str):
                    messages.append({"role": "user", "content": content})
                else:
                    content_parts: list[dict[str, Any]] = []
                    for block in content:
                        block_type = getattr(block, "type", None)
                        if block_type == "text":
                            content_parts.append({"type": "text", "text": getattr(block, "text", "")})
                        elif block_type == "image":
                            mime_type = getattr(block, "mime_type", "image/png")
                            data = getattr(block, "data", "")
                            content_parts.append(
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{data}",
                                    },
                                }
                            )
                    messages.append({"role": "user", "content": content_parts})
            elif message.role == "assistant":
                content_parts: list[TextContent | ThinkingContent | ToolCall] = list(message.content)
                text = "".join(
                    block.text
                    for block in content_parts
                    if isinstance(block, TextContent)
                )
                thinking = "".join(
                    block.thinking
                    for block in content_parts
                    if isinstance(block, ThinkingContent)
                )
                tool_calls = [
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.arguments, ensure_ascii=False),
                        },
                    }
                    for block in content_parts
                    if isinstance(block, ToolCall)
                ]
                payload: dict[str, Any] = {"role": "assistant"}
                if text:
                    payload["content"] = text
                elif thinking and self.compat.requires_thinking_as_text:
                    payload["content"] = thinking
                else:
                    payload["content"] = ""
                if tool_calls:
                    payload["tool_calls"] = tool_calls
                messages.append(payload)
            elif message.role == "toolResult":
                tool_message = message  # type: ignore[assignment]
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": getattr(tool_message, "tool_call_id", ""),
                        "name": getattr(tool_message, "tool_name", ""),
                        "content": _join_text_content(getattr(tool_message, "content", [])),
                    }
                )

        return {"messages": messages}

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
        max_tokens_field = self.compat.max_tokens_field or "max_completion_tokens"
        if options.max_tokens is not None:
            payload[max_tokens_field] = options.max_tokens
        elif model.max_output_tokens is not None:
            payload[max_tokens_field] = model.max_output_tokens
        if options.temperature is not None:
            payload["temperature"] = options.temperature
        if context.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in context.tools
            ]
        headers = {"content-type": "application/json", **(options.headers or {})}
        if options.api_key:
            headers["authorization"] = f"Bearer {options.api_key}"
        return ProviderRequest(
            url=f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=getattr(options, "timeout", None),
            metadata={"provider": "openai", "api": self.api},
        )

    def parse_chunk(self, chunk: StreamChunk, state: StreamParseState) -> None:
        data = chunk.data or {}
        if chunk.raw.strip() == "[DONE]" or data.get("text") == "[DONE]":
            state.set_stop_reason("stop")
            return
        if "error" in data:
            error = data.get("error")
            state.set_error(error.get("message") if isinstance(error, dict) else str(error))
            state.set_stop_reason("error")
            return

        choices = data.get("choices") or []
        if not choices:
            if "usage" in data:
                state.set_usage(data.get("usage"))
            return

        choice = choices[0] or {}
        delta = choice.get("delta") or {}
        if data.get("id"):
            state.set_response_id(data.get("id"))
        if delta.get("role") == "assistant":
            state.assistant_message.provider = self.name
            state.assistant_message.api = self.api
        content = delta.get("content")
        if content:
            apply_text_delta(state, content, 0)

        reasoning = (
            delta.get("reasoning")
            or delta.get("thinking")
            or delta.get("reasoning_content")
            or delta.get("reasoning_text")
        )
        if reasoning:
            apply_thinking_delta(state, reasoning, 0)

        tool_calls = delta.get("tool_calls") or []
        for tool_call in tool_calls:
            index = int(tool_call.get("index", 0))
            current = state.emit_tool_call_start(index)
            if tool_call.get("id"):
                current.id = tool_call["id"]
            function = tool_call.get("function") or {}
            if function.get("name"):
                current.name = function["name"]
            arguments = function.get("arguments") or tool_call.get("arguments") or ""
            if arguments:
                current = state.append_tool_call_delta(index, arguments)

        finish_reason = choice.get("finish_reason")
        if finish_reason:
            if finish_reason == "tool_calls":
                state.set_stop_reason("toolUse")
            elif finish_reason == "length":
                state.set_stop_reason("length")
            elif finish_reason in {"stop", "content_filter"}:
                state.set_stop_reason("stop" if finish_reason == "stop" else "error")
            else:
                state.set_stop_reason(finish_reason)

        if "usage" in data:
            state.set_usage(data.get("usage"))
