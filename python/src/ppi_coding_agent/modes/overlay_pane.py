"""Overlay pane for the interactive coding-agent TUI."""

from __future__ import annotations

from dataclasses import dataclass

from .tui_state import TuiState, TuiOverlay, wrap_text


@dataclass(slots=True)
class OverlayPane:
    state: TuiState
    invalidated: bool = True

    def render(self, width: int) -> list[str]:
        rendered: list[str] = []
        for overlay in self.state.overlays[-2:]:
            title = f"[{overlay.title}]".ljust(min(width, len(overlay.title) + 2), "=")
            rendered.append(title[:width])
            rendered.extend(wrap_text(" | ".join(overlay.lines), width))
        self.invalidated = False
        return rendered

    def handle_input(self, data: str) -> None:
        return None

    def invalidate(self) -> None:
        self.invalidated = True
