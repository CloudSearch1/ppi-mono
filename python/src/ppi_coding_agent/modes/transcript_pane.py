"""Transcript pane for the interactive coding-agent TUI."""

from __future__ import annotations

from dataclasses import dataclass

from ppi_ai import TextContent
from ppi_coding_agent.core.session_types import SessionEntry

from .environment import ModeEnvironment
from .tui_state import TuiState, format_entry, wrap_text


@dataclass(slots=True)
class TranscriptPane:
    env: ModeEnvironment
    state: TuiState
    invalidated: bool = True

    def render(self, width: int, height: int) -> list[str]:
        transcript: list[str] = []
        entries = self.env.sessions.get_entries()[-self.state.scrollback :]
        for entry in entries:
            transcript.extend(wrap_text(format_entry(entry), width))
        if not entries:
            transcript.append("(no messages yet)")
        transcript.append("")
        transcript.extend(wrap_text(f"> {self.state.input_buffer}", width))
        max_lines = max(4, height)
        self.invalidated = False
        return transcript[-max_lines:]

    def handle_input(self, data: str) -> None:
        return None

    def invalidate(self) -> None:
        self.invalidated = True
