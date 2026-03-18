"""Terminal adapters."""

from __future__ import annotations

import os
import platform
import sys
import threading
import time
from dataclasses import dataclass
from dataclasses import field
from queue import Queue
from select import select
from typing import Callable

from .keys import Key, normalize_key
from .types import Terminal


@dataclass(slots=True)
class ProcessTerminal:
    """Lightweight line-oriented process terminal adapter."""

    _stop_event: threading.Event = field(init=False, repr=False)
    _input_thread: threading.Thread | None = None
    _stdin_queue: Queue[str] | None = None
    _raw_mode_enabled: bool = False
    _original_termios: tuple | None = None

    def __post_init__(self) -> None:
        self._stop_event = threading.Event()
        self._stdin_queue = Queue()

    def start(self, on_input: Callable[[str], None], on_resize: Callable[[], None]) -> None:
        def reader() -> None:
            if platform.system().lower().startswith("win"):
                self._read_windows_keys(on_input)
            else:
                self._read_stream_lines(on_input)

        if self._enable_raw_mode():
            self._raw_mode_enabled = True
        self._input_thread = threading.Thread(target=reader, name="pimono-terminal-reader", daemon=True)
        self._input_thread.start()
        on_resize()

    def stop(self) -> None:
        self._stop_event.set()
        if self._input_thread is not None and self._input_thread.is_alive():
            self._input_thread.join(timeout=0.5)
        self._restore_mode()

    def is_interactive(self) -> bool:
        return bool(getattr(sys.stdin, "isatty", lambda: False)())

    def _read_stream_lines(self, on_input: Callable[[str], None]) -> None:
        if self._raw_mode_enabled:
            self._read_raw_unix(on_input)
            return
        while not self._stop_event.is_set():
            try:
                line = sys.stdin.readline()
            except Exception:
                break
            if line == "":
                break
            on_input(line.rstrip("\n"))

    def _read_windows_keys(self, on_input: Callable[[str], None]) -> None:
        try:
            import msvcrt
        except Exception:
            self._read_stream_lines(on_input)
            return

        while not self._stop_event.is_set():
            if not msvcrt.kbhit():
                time.sleep(0.01)
                continue
            ch = msvcrt.getwch()
            if ch in {"\r", "\n"}:
                on_input(Key.enter)
                continue
            if ch == "\t":
                on_input(Key.tab)
                continue
            if ch in {"\x08", "\x7f"}:
                on_input(Key.backspace)
                continue
            if ch == "\x1b":
                on_input(Key.escape)
                continue
            if ch in {"\x00", "\xe0"}:
                code = msvcrt.getwch()
                arrow_map = {
                    "H": Key.up,
                    "P": Key.down,
                    "K": Key.left,
                    "M": Key.right,
                }
                on_input(arrow_map.get(code, code))
                continue
            if len(ch) == 1 and 1 <= ord(ch) <= 26:
                on_input(Key.ctrl(chr(ord("a") + ord(ch) - 1)))
                continue
                on_input(ch)

    def _read_raw_unix(self, on_input: Callable[[str], None]) -> None:
        while not self._stop_event.is_set():
            readable, _, _ = select([sys.stdin], [], [], 0.05)
            if not readable:
                continue
            token = self._read_unix_token()
            if token is None:
                continue
            if token == Key.paste_start:
                pasted = self._read_bracketed_paste()
                if pasted:
                    on_input(pasted)
                continue
            on_input(token)

    def _read_unix_token(self) -> str | None:
        try:
            ch = sys.stdin.read(1)
        except Exception:
            return None
        if not ch:
            return None
        if ch != "\x1b":
            return normalize_key(ch)

        sequence = ch
        while True:
            readable, _, _ = select([sys.stdin], [], [], 0.01)
            if not readable:
                return normalize_key(sequence)
            try:
                nxt = sys.stdin.read(1)
            except Exception:
                return normalize_key(sequence)
            if not nxt:
                return normalize_key(sequence)
            sequence += nxt
            if sequence.endswith("~") or sequence[-1].isalpha():
                return normalize_key(sequence)

    def _read_bracketed_paste(self) -> str:
        chunks: list[str] = []
        while not self._stop_event.is_set():
            readable, _, _ = select([sys.stdin], [], [], 0.05)
            if not readable:
                continue
            try:
                chunk = sys.stdin.read(1)
            except Exception:
                break
            if not chunk:
                break
            chunks.append(chunk)
            if "".join(chunks).endswith("\x1b[201~"):
                text = "".join(chunks)
                return text[:-6]
        return "".join(chunks)

    def _enable_raw_mode(self) -> bool:
        if platform.system().lower().startswith("win"):
            return False
        try:
            import termios
            import tty
        except Exception:
            return False
        try:
            fd = sys.stdin.fileno()
            self._original_termios = termios.tcgetattr(fd)
            tty.setcbreak(fd)
            return True
        except Exception:
            self._original_termios = None
            return False

    def _restore_mode(self) -> None:
        if self._original_termios is None:
            return
        try:
            import termios

            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._original_termios)
        except Exception:
            pass
        finally:
            self._original_termios = None

    def write(self, data: str) -> None:
        sys.stdout.write(data)
        sys.stdout.flush()

    def move_by(self, lines: int) -> None:
        if lines > 0:
            sys.stdout.write(f"\x1b[{lines}A")
        elif lines < 0:
            sys.stdout.write(f"\x1b[{abs(lines)}B")
        sys.stdout.flush()

    def hide_cursor(self) -> None:
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()

    def show_cursor(self) -> None:
        sys.stdout.write("\x1b[?25h")
        sys.stdout.flush()

    def clear_line(self) -> None:
        sys.stdout.write("\x1b[2K\r")
        sys.stdout.flush()

    def clear_from_cursor(self) -> None:
        sys.stdout.write("\x1b[0J")
        sys.stdout.flush()

    def clear_screen(self) -> None:
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.flush()
