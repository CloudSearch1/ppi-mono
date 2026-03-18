"""Composer pane for the interactive coding-agent TUI."""

from __future__ import annotations

from dataclasses import dataclass

from .tui_state import TuiState


@dataclass(slots=True)
class ComposerPane:
    state: TuiState
    invalidated: bool = True

    def render(self, width: int) -> list[str]:
        commands = " /help | /describe | /schemas | /validate | /reload | /session | /quit"
        status = f"status: {self.state.status}"
        self.invalidated = False
        return [commands[:width], status[:width]]

    def handle_input(self, data: str) -> None:
        return None

    def invalidate(self) -> None:
        self.invalidated = True
