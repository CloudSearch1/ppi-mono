"""Anthropic provider adapter template."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import AssistantMessage, Context, Model, StreamOptions, TextContent, ThinkingContent, ToolCall
from ..registry import AssistantMessageStream
from .common import ProviderRequest, StreamChunk, StreamParseState, apply_text_delta, apply_thinking_delta, apply_tool_call_delta
from .base import BaseProvider


@dataclass(slots=True)
class AnthropicProvider(BaseProvider):
    name: str = "anthropic"
    api: str = "anthropic"
    metadata: dict[str, Any] = field(default_factory=dict)

    async def stream(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessageStream:
        """Start a streaming Anthropic request."""
        return await BaseProvider.stream(self, model, context, options)

    async def complete(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessage:
        """Run a one-shot Anthropic completion."""
        return await BaseProvider.complete(self, model, context, options)

    def to_messages_payload(self, context: Context) -> list[dict[str, Any]]:
        """Convert shared context into Anthropic message payload shape."""
        messages: list[dict[str, Any]] = []
        for message in context.messages:
            if message.role == "user":
                content = message.content
                if isinstance(content, str):
                    payload_content = [{"type": "text", "text": content}]
                else:
                    payload_content = []
                    for block in content:
                        if getattr(block, "type", None) == "text":
                            payload_content.append({"type": "text", "text": getattr(block, "text", "")})
                        elif getattr(block, "type", None) == "image":
                            payload_content.append({"type": "image", "source": {"type": "base64", "media_type": getattr(block, "mime_type", "image/png"), "data": getattr(block, "data", "")}})
                messages.append({"role": "user", "content": payload_content})
            elif message.role == "assistant":
                payload_content = []
                for block in message.content:
                    if isinstance(block, TextContent):
                        payload_content.append({"type": "text", "text": block.text})
                    elif isinstance(block, ThinkingContent):
                        payload_content.append({"type": "thinking", "thinking": block.thinking, "redacted": block.redacted})
                    elif isinstance(block, ToolCall):
                        payload_content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.arguments})
                messages.append({"role": "assistant", "content": payload_content})
            elif message.role == "toolResult":
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": getattr(message, "tool_call_id", ""),
                                "content": getattr(message, "content", []),
                                "is_error": getattr(message, "is_error", False),
                            }
                        ],
                    }
                )
        return messages

    def build_request(self, model: Model, context: Context, options: StreamOptions | None = None) -> ProviderRequest:
        options = self.normalize_options(options)
        base_url = model.base_url or "https://api.anthropic.com/v1"
        payload: dict[str, Any] = {
            "model": model.id,
            "max_tokens": options.max_tokens or model.max_output_tokens or 4096,
            "messages": self.to_messages_payload(context),
            "system": context.system_prompt,
            "stream": True,
        }
        if options.temperature is not None:
            payload["temperature"] = options.temperature
        if options.reasoning is not None and options.reasoning != "off":
            payload["thinking"] = {"type": "enabled", "budget_tokens": options.thinking_budgets.get(options.reasoning, 0)}
        return ProviderRequest(
            url=f"{base_url.rstrip('/')}/messages",
            headers={
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
                **(options.headers or {}),
            },
            json=payload,
            stream=True,
            timeout=getattr(options, "timeout", None),
            metadata={"provider": "anthropic"},
        )

    def parse_chunk(self, chunk: StreamChunk, state: StreamParseState) -> None:
        data = chunk.data or {}
        event_type = chunk.event or data.get("type")
        if event_type in {"message_start", "start"}:
            state.assistant_message.provider = "anthropic"
            state.assistant_message.api = "anthropic"
            state.set_response_id(data.get("message", {}).get("id") or data.get("id"))
            return
        if event_type == "content_block_delta":
            block = data.get("delta", {})
            block_type = data.get("content_block", {}).get("type")
            index = int(data.get("index", 0))
            if block_type == "text" or block.get("type") == "text_delta":
                apply_text_delta(state, block.get("text", "") or block.get("delta", ""))
            elif block_type == "thinking" or block.get("type") == "thinking_delta":
                apply_thinking_delta(state, block.get("thinking", "") or block.get("delta", ""))
            elif block_type == "tool_use":
                tool_call = apply_tool_call_delta(state, index, block.get("input_json", "") or block.get("delta", ""))
                tool_call.name = data.get("content_block", {}).get("name", tool_call.name)
                tool_call.id = data.get("content_block", {}).get("id", tool_call.id)
            return
        if event_type == "content_block_start":
            block = data.get("content_block", {})
            index = int(data.get("index", 0))
            if block.get("type") == "tool_use":
                tool_call = state.emit_tool_call_start(index)
                tool_call.id = block.get("id", tool_call.id)
                tool_call.name = block.get("name", tool_call.name)
                return
        if event_type == "message_delta":
            message = data.get("message", {})
            if "stop_reason" in message:
                state.set_stop_reason(message.get("stop_reason"))
            if "usage" in message:
                state.set_usage(message.get("usage"))
            return
        if event_type in {"message_stop", "done"}:
            state.set_stop_reason(data.get("stop_reason") or state.assistant_message.stop_reason)
