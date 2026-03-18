"""Common TUI types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Protocol, TypeAlias


class Component(Protocol):
    def render(self, width: int) -> list[str]:
        ...

    def handle_input(self, data: str) -> None:
        ...

    def invalidate(self) -> None:
        ...


class Focusable(Protocol):
    focused: bool


OverlayAnchor: TypeAlias = Literal[
    "center",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
    "top-center",
    "bottom-center",
    "left-center",
    "right-center",
]


@dataclass(slots=True)
class OverlayOptions:
    width: int | str | None = None
    min_width: int | None = None
    max_height: int | str | None = None
    anchor: OverlayAnchor = "center"
    offset_x: int = 0
    offset_y: int = 0
    row: int | str | None = None
    col: int | str | None = None
    margin: int | None = None
    visible: Callable[[int, int], bool] | None = None
    non_capturing: bool = False


class OverlayHandle(Protocol):
    def hide(self) -> None:
        ...

    def set_hidden(self, hidden: bool) -> None:
        ...

    def is_hidden(self) -> bool:
        ...

    def focus(self) -> None:
        ...

    def unfocus(self) -> None:
        ...

    def is_focused(self) -> bool:
        ...


CURSOR_MARKER = "\x1b_pi:c\x07"


class Terminal(Protocol):
    def start(self, on_input: Callable[[str], None], on_resize: Callable[[], None]) -> None:
        ...

    def stop(self) -> None:
        ...

    def write(self, data: str) -> None:
        ...

    def move_by(self, lines: int) -> None:
        ...

    def hide_cursor(self) -> None:
        ...

    def show_cursor(self) -> None:
        ...

    def clear_line(self) -> None:
        ...

    def clear_from_cursor(self) -> None:
        ...

    def clear_screen(self) -> None:
        ...
