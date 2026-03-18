"""Header pane for the interactive coding-agent TUI."""

from __future__ import annotations

from dataclasses import dataclass

from .environment import ModeEnvironment


@dataclass(slots=True)
class HeaderPane:
    env: ModeEnvironment
    invalidated: bool = True

    def render(self, width: int) -> list[str]:
        snapshot = self.env.describe()
        lines = [
            "pimono interactive workspace",
            f"cwd: {snapshot['cwd']}",
            f"session: {snapshot['session_id'] or 'new'}",
            f"model: {snapshot['default_provider']}/{snapshot['default_model']}",
            f"schemas: {snapshot['schema_count']} registered",
        ]
        self.invalidated = False
        return [line[:width] for line in lines]

    def handle_input(self, data: str) -> None:
        return None

    def invalidate(self) -> None:
        self.invalidated = True
