"""Shared TUI state and formatting helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ppi_ai import TextContent
from ppi_coding_agent.core.session_types import SessionEntry
from ppi_tui import OverlayOptions


@dataclass(slots=True)
class TuiCommandResult:
    action: str
    message: str
    refresh: bool = True
    exit_requested: bool = False
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TuiOverlay:
    title: str
    lines: list[str] = field(default_factory=list)
    options: OverlayOptions = field(default_factory=OverlayOptions)


@dataclass(slots=True)
class TuiState:
    input_buffer: str = ""
    status: str = "ready"
    overlays: list[TuiOverlay] = field(default_factory=list)
    scrollback: int = 16
    paused: bool = False
    history: list[str] = field(default_factory=list)
    history_index: int = 0


def wrap_text(text: str, width: int) -> list[str]:
    if width <= 0:
        return [text]
    if not text:
        return [""]
    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        if not raw_line:
            lines.append("")
            continue
        line = raw_line
        while len(line) > width:
            lines.append(line[:width])
            line = line[width:]
        lines.append(line)
    return lines


def format_entry(entry: SessionEntry) -> str:
    kind = getattr(entry, "type", "entry")
    message = getattr(entry, "message", None)
    if message is None:
        return f"[{kind}] {entry.id}"
    role = getattr(message, "role", kind)
    if role == "user":
        content = getattr(message, "content", "")
        text = content if isinstance(content, str) else " ".join(
            getattr(block, "text", "") for block in content if getattr(block, "type", None) == "text"
        )
        return f"[user] {text}"
    if role == "assistant":
        blocks = getattr(message, "content", [])
        text = "".join(getattr(block, "text", "") for block in blocks if isinstance(block, TextContent))
        return f"[assistant] {text}" if text else "[assistant]"
    if role == "toolResult":
        return f"[tool] {getattr(message, 'tool_name', '')}"
    return f"[{role}] {entry.id}"
