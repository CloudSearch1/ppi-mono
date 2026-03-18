"""Rendering helpers."""

from __future__ import annotations

from typing import Any


def visible_width(text: str) -> int:
    raise NotImplementedError


def truncate_to_width(text: str, width: int, ellipsis: str = "...") -> str:
    raise NotImplementedError


def wrap_text_with_ansi(text: str, width: int) -> list[str]:
    raise NotImplementedError
