"""Key parsing helpers."""

from __future__ import annotations

import re
from typing import TypeAlias

KeyId: TypeAlias = str

_CSI_PATTERN = re.compile(r"^\x1b\[(?P<body>[0-9;?]*)(?P<final>[A-Za-z~])$")


class Key:
    enter = "enter"
    escape = "escape"
    tab = "tab"
    backspace = "backspace"
    up = "up"
    down = "down"
    left = "left"
    right = "right"
    paste_start = "paste_start"
    paste_end = "paste_end"

    @staticmethod
    def ctrl(key: str) -> str:
        return f"ctrl+{key}"


def normalize_key(data: str) -> str:
    if not data:
        return ""
    if data in {"\r", "\n"}:
        return Key.enter
    if data == "\t":
        return Key.tab
    if data in {"\x08", "\x7f"}:
        return Key.backspace
    if data == "\x1b":
        return Key.escape
    if data in {"\x03"}:
        return Key.ctrl("c")
    if data in {"\x04"}:
        return Key.ctrl("d")
    if data in {"\x12"}:
        return Key.ctrl("r")
    if data in {"\x0c"}:
        return Key.ctrl("l")
    if data.startswith("\x1b[200~"):
        return Key.paste_start
    if data.startswith("\x1b[201~"):
        return Key.paste_end
    if data.startswith("\x1b["):
        match = _CSI_PATTERN.match(data)
        if match:
            final = match.group("final")
            mapping = {
                "A": Key.up,
                "B": Key.down,
                "C": Key.right,
                "D": Key.left,
            }
            return mapping.get(final, data)
    if len(data) == 1 and 1 <= ord(data) <= 26:
        return Key.ctrl(chr(ord("a") + ord(data) - 1))
    return data


def matches_key(data: str, key_id: KeyId) -> bool:
    return normalize_key(data) == key_id
