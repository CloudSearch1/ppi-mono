"""Tool renderer registry contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ToolRenderResult:
    content: Any
    is_custom: bool = False


class ToolRenderer(Protocol):
    def render(self, params: Any, result: Any, is_streaming: bool) -> ToolRenderResult:
        ...


_renderers: dict[str, ToolRenderer] = {}


def register_tool_renderer(tool_name: str, renderer: ToolRenderer) -> None:
    _renderers[tool_name] = renderer


def get_tool_renderer(tool_name: str) -> ToolRenderer | None:
    return _renderers.get(tool_name)
