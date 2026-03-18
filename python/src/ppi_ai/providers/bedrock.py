"""Amazon Bedrock provider adapter template."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..models import (
    AssistantMessage,
    Context,
    Model,
    StreamOptions,
    TextContent,
    ThinkingContent,
    ToolCall,
    ToolResultMessage,
)
from ..registry import AssistantMessageStream
from .base import BaseProvider
from .common import ProviderRequest, StreamChunk, StreamParseState, apply_text_delta, apply_thinking_delta
from ..events import TextStartEvent, ThinkingStartEvent


@dataclass(slots=True)
class BedrockOptions(StreamOptions):
    region: str | None = None
    profile: str | None = None
    tool_choice: str | None = None
    prompt_mode: str | None = None
    reasoning: str | None = None
    thinking_budgets: dict[str, int] = field(default_factory=dict)
    interleaved_thinking: bool = False


@dataclass(slots=True)
class BedrockProvider(BaseProvider):
    name: str = "bedrock"
    api: str = "bedrock-converse-stream"
    metadata: dict[str, Any] = field(default_factory=dict)

    async def stream(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessageStream:
        return await BaseProvider.stream(self, model, context, options)

    async def complete(
        self, model: Model, context: Context, options: StreamOptions | None = None
    ) -> AssistantMessage:
        return await BaseProvider.complete(self, model, context, options)

    def to_messages_payload(self, context: Context) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for message in context.messages:
            if message.role == "user":
                content = message.content
                if isinstance(content, str):
                    messages.append({"role": "user", "content": [{"text": content}]})
                else:
                    blocks: list[dict[str, Any]] = []
                    for block in content:
                        if getattr(block, "type", None) == "text":
                            blocks.append({"text": getattr(block, "text", "")})
                        elif getattr(block, "type", None) == "image":
                            blocks.append(
                                {
                                    "image": {
                                        "format": getattr(block, "mime_type", "image/png").split("/")[-1],
                                        "source": {"bytes": getattr(block, "data", "")},
                                    }
                                }
                            )
                    messages.append({"role": "user", "content": blocks})
            elif message.role == "assistant":
                blocks: list[dict[str, Any]] = []
                for block in message.content:
                    if isinstance(block, TextContent):
                        blocks.append({"text": block.text})
                    elif isinstance(block, ThinkingContent):
                        blocks.append({"reasoningText": {"text": block.thinking}})
                    elif isinstance(block, ToolCall):
                        blocks.append(
                            {
                                "toolUse": {
                                    "toolUseId": block.id,
                                    "name": block.name,
                                    "input": block.arguments,
                                }
                            }
                        )
                messages.append({"role": "assistant", "content": blocks})
            elif message.role == "toolResult":
                tool_message = message  # type: ignore[assignment]
                blocks = []
                for block in getattr(tool_message, "content", []):
                    if isinstance(block, TextContent):
                        blocks.append({"text": block.text})
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "toolResult": {
                                    "toolUseId": getattr(tool_message, "tool_call_id", ""),
                                    "content": blocks,
                                    "status": "error" if getattr(tool_message, "is_error", False) else "success",
                                }
                            }
                        ],
                    }
                )
        return messages

    def build_request(self, model: Model, context: Context, options: StreamOptions | None = None) -> ProviderRequest:
        options = self.normalize_options(options)
        payload: dict[str, Any] = {
            "modelId": model.id,
            "messages": self.to_messages_payload(context),
            "system": [{"text": context.system_prompt}] if context.system_prompt else [],
            "inferenceConfig": {
                "maxTokens": options.max_tokens or model.max_output_tokens or 4096,
                **({"temperature": options.temperature} if options.temperature is not None else {}),
            },
            "stream": True,
        }
        if context.tools:
            payload["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": {"json": tool.parameters},
                        }
                    }
                    for tool in context.tools
                ]
            }
        reasoning = getattr(options, "reasoning", None)
        if reasoning:
            payload["additionalModelRequestFields"] = {"reasoning": {"effort": reasoning}}
        return ProviderRequest(
            url=(model.base_url or "https://bedrock-runtime.amazonaws.com").rstrip("/") + "/converse-stream",
            headers={"content-type": "application/json", **(options.headers or {})},
            json=payload,
            stream=True,
            timeout=getattr(options, "timeout", None),
            metadata={"provider": "bedrock", "region": getattr(options, "region", None)},
        )

    def parse_chunk(self, chunk: StreamChunk, state: StreamParseState) -> None:
        data = chunk.data or {}
        event_type = chunk.event or data.get("type")
        if event_type in {"message_start", "messageStart"}:
            state.assistant_message.provider = self.name
            state.assistant_message.api = self.api
            state.set_response_id(data.get("messageId") or data.get("message_id") or data.get("id"))
            return
        if event_type in {"content_block_start", "contentBlockStart"}:
            index = int(data.get("index", 0))
            block = data.get("content_block") or data.get("contentBlock") or {}
            block_type = block.get("type") or block.get("contentBlockType")
            if block_type in {"text", "text"}:
                if index not in state.text_started_indices:
                    state.text_started_indices.add(index)
                    state.emit(TextStartEvent(content_index=index, partial=state.build_message()))
            elif block_type in {"reasoning", "thinking"}:
                if index not in state.thinking_started_indices:
                    state.thinking_started_indices.add(index)
                    state.emit(ThinkingStartEvent(content_index=index, partial=state.build_message()))
            elif block_type in {"toolUse", "tool_use"}:
                call = state.emit_tool_call_start(index)
                call.id = block.get("toolUseId", call.id)
                call.name = block.get("name", call.name)
            return
        if event_type in {"content_block_delta", "contentBlockDelta"}:
            index = int(data.get("index", 0))
            delta = data.get("delta") or {}
            if "text" in delta:
                apply_text_delta(state, delta.get("text", ""), index)
            elif "reasoningText" in delta:
                reasoning = delta.get("reasoningText") or {}
                apply_thinking_delta(state, reasoning.get("text", ""), index)
            elif "toolUse" in delta:
                tool_use = delta.get("toolUse") or {}
                call = state.emit_tool_call_start(index)
                call.id = tool_use.get("toolUseId", call.id)
                call.name = tool_use.get("name", call.name)
                if "input" in tool_use:
                    current = state.append_tool_call_delta(index, json.dumps(tool_use.get("input") or {}, ensure_ascii=False))
                    current.arguments = tool_use.get("input") or {}
            return
        if event_type in {"content_block_stop", "contentBlockStop"}:
            index = int(data.get("index", 0))
            if index < len(state.tool_calls):
                state.emit_tool_call_end(index, state.tool_calls[index])
            return
        if event_type in {"message_stop", "messageStop"}:
            stop_reason = data.get("stop_reason") or data.get("stopReason")
            if stop_reason:
                state.set_stop_reason(stop_reason)
            if data.get("usage"):
                state.set_usage(data.get("usage"))
            return
        if event_type in {"metadata", "Metadata"}:
            metadata = data.get("usage") or data.get("metadata") or {}
            if metadata:
                state.set_usage(metadata if isinstance(metadata, dict) else {})
            return
        if event_type in {"error", "exception"}:
            state.set_error(data.get("message") or data.get("error") or "bedrock stream error")
            state.set_stop_reason("error")
