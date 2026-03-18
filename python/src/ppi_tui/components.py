"""High-level TUI components."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .autocomplete import AutocompleteProvider
from .types import Component, Focusable, OverlayHandle, OverlayOptions, Terminal


@dataclass(slots=True)
class Container:
    children: list[Component] = field(default_factory=list)

    def add_child(self, component: Component) -> None:
        self.children.append(component)

    def remove_child(self, component: Component) -> None:
        self.children.remove(component)

    def render(self, width: int) -> list[str]:
        return []

    def handle_input(self, data: str) -> None:
        return None

    def invalidate(self) -> None:
        return None


class TUI(Container):
    def __init__(self, terminal: Terminal) -> None:
        super().__init__()
        self.terminal = terminal

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def request_render(self) -> None:
        raise NotImplementedError

    def show_overlay(self, component: Component, options: OverlayOptions | None = None) -> OverlayHandle:
        raise NotImplementedError


class Input:
    def __init__(self) -> None:
        self.value = ""
        self.focused = False

    def render(self, width: int) -> list[str]:
        raise NotImplementedError


class Editor(Input):
    def set_autocomplete_provider(self, provider: AutocompleteProvider) -> None:
        raise NotImplementedError


class SelectList:
    def __init__(self) -> None:
        self.items: list[Any] = []

    def render(self, width: int) -> list[str]:
        raise NotImplementedError


class Markdown:
    def __init__(self, text: str = "") -> None:
        self.text = text

    def render(self, width: int) -> list[str]:
        raise NotImplementedError
