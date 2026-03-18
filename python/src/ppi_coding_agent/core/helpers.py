"""Internal helper functions for the coding-agent core layer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dataclasses import asdict, is_dataclass

from ppi_ai import AssistantMessage, ImageContent, Message, TextContent, ThinkingContent, ToolCall, ToolResultMessage, UserMessage

from .types import ResourceKind, SessionBranchSummaryEntry, SessionCompactionEntry, SessionCustomEntry, SessionCustomMessageEntry, SessionEntry, SessionHeader, SessionInfoEntry, SessionLabelEntry, SessionMessageEntry


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "entry") -> str:
    return f"{prefix}_{uuid4().hex}"


def session_base_dir(cwd: str, session_dir: str | None) -> Path | None:
    if session_dir:
        return Path(session_dir)
    return Path(cwd) / ".ppi" / "sessions"


def session_path(cwd: str, session_dir: str | None, session_id: str) -> Path | None:
    base_dir = session_base_dir(cwd, session_dir)
    if base_dir is None:
        return None
    return base_dir / f"{session_id}.jsonl"


def latest_session_path(cwd: str, session_dir: str | None) -> Path | None:
    base_dir = session_base_dir(cwd, session_dir)
    if base_dir is None or not base_dir.exists():
        return None
    candidates = sorted(base_dir.glob("*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def get_nested(settings: Any, path: str, default: Any = None) -> Any:
    current: Any = settings
    for part in path.split("."):
        if hasattr(current, part):
            current = getattr(current, part, default)
        elif isinstance(current, dict):
            current = current.get(part, default)
        else:
            return default
    return current


def infer_kind_from_path(path: Path) -> ResourceKind:
    parts = {part.lower() for part in path.parts}
    if "skills" in parts:
        return "skill"
    if "prompts" in parts:
        return "prompt"
    if "themes" in parts:
        return "theme"
    if "extensions" in parts:
        return "extension"
    if "agents" in parts:
        return "agent"
    if "packages" in parts:
        return "package"
    return "config"


def serialize_message(message: Message | AssistantMessage) -> dict[str, Any]:
    if isinstance(message, AssistantMessage):
        content: list[dict[str, Any]] = []
        for block in message.content:
            if isinstance(block, TextContent):
                content.append(asdict(block))
            elif isinstance(block, ThinkingContent):
                content.append(asdict(block))
            elif isinstance(block, ToolCall):
                content.append(asdict(block))
        return {
            "role": "assistant",
            "content": content,
            "api": message.api,
            "provider": message.provider,
            "model": message.model,
            "response_id": message.response_id,
            "usage": asdict(message.usage),
            "stop_reason": message.stop_reason,
            "error_message": message.error_message,
            "timestamp": message.timestamp,
        }
    if isinstance(message, UserMessage):
        content = message.content
        if isinstance(content, str):
            serialized_content: Any = content
        else:
            serialized_content = [asdict(block) for block in content]
        return {"role": "user", "content": serialized_content, "timestamp": message.timestamp}
    if isinstance(message, ToolResultMessage):
        return {
            "role": "toolResult",
            "tool_call_id": message.tool_call_id,
            "tool_name": message.tool_name,
            "content": [asdict(block) for block in message.content],
            "details": message.details,
            "is_error": message.is_error,
            "timestamp": message.timestamp,
        }
    return {"role": getattr(message, "role", "unknown"), "payload": asdict(message) if is_dataclass(message) else message}


def deserialize_message(data: dict[str, Any]) -> Message | AssistantMessage | None:
    role = data.get("role")
    if role == "user":
        content = data.get("content", "")
        if isinstance(content, list):
            blocks: list[TextContent | ImageContent] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    blocks.append(TextContent(text=block.get("text", ""), text_signature=block.get("text_signature")))
                elif block.get("type") == "image":
                    blocks.append(ImageContent(data=block.get("data", ""), mime_type=block.get("mime_type", "image/png")))
            content_value: str | list[TextContent | ImageContent] = blocks
        else:
            content_value = str(content)
        return UserMessage(content=content_value, timestamp=int(data.get("timestamp", 0)))
    if role == "assistant":
        content_blocks: list[TextContent | ThinkingContent | ToolCall] = []
        for block in data.get("content", []) or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                content_blocks.append(TextContent(text=block.get("text", ""), text_signature=block.get("text_signature")))
            elif block.get("type") == "thinking":
                content_blocks.append(
                    ThinkingContent(
                        thinking=block.get("thinking", ""),
                        thinking_signature=block.get("thinking_signature"),
                        redacted=bool(block.get("redacted", False)),
                    )
                )
            elif block.get("type") == "toolCall":
                content_blocks.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("arguments", {}) or {},
                        thought_signature=block.get("thought_signature"),
                    )
                )
        message = AssistantMessage(
            content=content_blocks,
            api=data.get("api", ""),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            response_id=data.get("response_id"),
            stop_reason=data.get("stop_reason", "stop"),
            error_message=data.get("error_message"),
            timestamp=int(data.get("timestamp", 0)),
        )
        usage = data.get("usage")
        if isinstance(usage, dict):
            message.usage.input = int(usage.get("input", usage.get("input_tokens", 0)))
            message.usage.output = int(usage.get("output", usage.get("output_tokens", 0)))
            message.usage.cache_read = int(usage.get("cache_read", usage.get("cache_read_tokens", 0)))
            message.usage.cache_write = int(usage.get("cache_write", usage.get("cache_write_tokens", 0)))
            message.usage.total_tokens = int(usage.get("total_tokens", 0))
        return message
    if role == "toolResult":
        content_blocks: list[TextContent | ImageContent] = []
        for block in data.get("content", []) or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                content_blocks.append(TextContent(text=block.get("text", ""), text_signature=block.get("text_signature")))
            elif block.get("type") == "image":
                content_blocks.append(ImageContent(data=block.get("data", ""), mime_type=block.get("mime_type", "image/png")))
        return ToolResultMessage(
            tool_call_id=data.get("tool_call_id", ""),
            tool_name=data.get("tool_name", ""),
            content=content_blocks,
            details=data.get("details", {}) or {},
            is_error=bool(data.get("is_error", False)),
            timestamp=int(data.get("timestamp", 0)),
        )
    return None


def entry_to_record(entry: SessionEntry) -> dict[str, Any]:
    record = {
        "type": entry.type,
        "id": entry.id,
        "parent_id": entry.parent_id,
        "timestamp": entry.timestamp,
    }
    if isinstance(entry, SessionMessageEntry):
        record["message"] = serialize_message(entry.message) if entry.message is not None else None
    elif isinstance(entry, SessionCompactionEntry):
        record.update({"summary": entry.summary, "first_kept_entry_id": entry.first_kept_entry_id, "tokens_before": entry.tokens_before, "details": entry.details})
    elif isinstance(entry, SessionBranchSummaryEntry):
        record.update({"summary": entry.summary, "details": entry.details})
    elif isinstance(entry, SessionCustomEntry):
        record.update({"custom_type": entry.custom_type, "data": entry.data})
    elif isinstance(entry, SessionCustomMessageEntry):
        record.update({"custom_type": entry.custom_type, "content": entry.content, "display": entry.display, "details": entry.details})
    elif isinstance(entry, SessionLabelEntry):
        record["label"] = entry.label
    elif isinstance(entry, SessionInfoEntry):
        record["name"] = entry.name
    return record


def record_to_entry(record: dict[str, Any]) -> SessionEntry:
    entry_type = record.get("type", "custom")
    common = {
        "id": record.get("id", new_id("entry")),
        "parent_id": record.get("parent_id"),
        "timestamp": record.get("timestamp", now_iso()),
    }
    if entry_type == "message":
        return SessionMessageEntry(**common, message=deserialize_message(record.get("message") or {}) if record.get("message") else None)
    if entry_type == "compaction":
        return SessionCompactionEntry(
            **common,
            summary=record.get("summary", ""),
            first_kept_entry_id=record.get("first_kept_entry_id", ""),
            tokens_before=int(record.get("tokens_before", 0)),
            details=record.get("details", {}) or {},
        )
    if entry_type == "branch_summary":
        return SessionBranchSummaryEntry(
            **common,
            summary=record.get("summary", ""),
            details=record.get("details", {}) or {},
        )
    if entry_type == "custom_message":
        return SessionCustomMessageEntry(
            **common,
            custom_type=record.get("custom_type", ""),
            content=record.get("content"),
            display=bool(record.get("display", True)),
            details=record.get("details"),
        )
    if entry_type == "label":
        return SessionLabelEntry(**common, label=record.get("label"))
    if entry_type == "session_info":
        return SessionInfoEntry(**common, name=record.get("name", ""))
    return SessionCustomEntry(**common, custom_type=record.get("custom_type", entry_type), data=record.get("data"))


def load_session_jsonl(path: Path) -> tuple[SessionHeader | None, list[SessionEntry]]:
    header: SessionHeader | None = None
    entries: list[SessionEntry] = []
    if not path.exists():
        return None, []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("type") == "session":
                header = SessionHeader(
                    id=record.get("id", ""),
                    timestamp=record.get("timestamp", ""),
                    cwd=record.get("cwd", ""),
                    parent_session=record.get("parent_session"),
                )
                continue
            entries.append(record_to_entry(record))
    return header, entries


def write_session_jsonl(path: Path, header: SessionHeader | None, entries: list[SessionEntry]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        if header is not None:
            handle.write(
                json.dumps(
                    {
                        "type": "session",
                        "version": header.version,
                        "id": header.id,
                        "timestamp": header.timestamp,
                        "cwd": header.cwd,
                        "parent_session": header.parent_session,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        for entry in entries:
            handle.write(json.dumps(entry_to_record(entry), ensure_ascii=False) + "\n")
