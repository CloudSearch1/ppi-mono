"""Top-level chat panel skeleton."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ChatPanel:
    """Placeholder for the browser chat composition layer."""

    def set_agent(self, agent: object, config: dict[str, object] | None = None) -> None:
        raise NotImplementedError
