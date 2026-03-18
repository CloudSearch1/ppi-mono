"""TUI composition for the interactive coding-agent shell."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from shutil import get_terminal_size
from threading import Event
from typing import Any

from ppi_ai import UserMessage
from ppi_tui import Key, ProcessTerminal, matches_key

from .composer_pane import ComposerPane
from .environment import ModeEnvironment
from .header_pane import HeaderPane
from .overlay_pane import OverlayPane
from .transcript_pane import TranscriptPane
from .tui_state import TuiCommandResult, TuiOverlay, TuiState, format_entry


@dataclass(slots=True)
class InteractiveTuiApp:
    env: ModeEnvironment
    terminal: ProcessTerminal = field(default_factory=ProcessTerminal)
    state: TuiState = field(default_factory=TuiState)
    header: HeaderPane | None = field(init=False, default=None)
    transcript: TranscriptPane | None = field(init=False, default=None)
    composer: ComposerPane | None = field(init=False, default=None)
    overlay: OverlayPane | None = field(init=False, default=None)
    _stop_event: Event = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.header = HeaderPane(self.env)
        self.transcript = TranscriptPane(self.env, self.state)
        self.composer = ComposerPane(self.state)
        self.overlay = OverlayPane(self.state)
        self._stop_event = Event()

    def bootstrap_lines(self) -> list[str]:
        return [
            "pimono interactive workspace",
            f"cwd: {self.env.paths.cwd}",
            f"session: {self.env.sessions.get_header().id if self.env.sessions.get_header() else 'new'}",
            f"model: {self.env.settings.get_default_provider()}/{self.env.settings.get_default_model()}",
            "type '/help' for commands",
        ]

    def render(self) -> str:
        size = get_terminal_size(fallback=(100, 30))
        width = max(40, size.columns)
        height = max(16, size.lines)
        header_lines = self.header.render(width) if self.header else []
        transcript_lines = (
            self.transcript.render(width, max(4, height - 10 - len(self.state.overlays) * 2))
            if self.transcript
            else []
        )
        composer_lines = self.composer.render(width) if self.composer else []
        overlay_lines = self.overlay.render(width) if self.overlay else []
        lines: list[str] = []
        lines.extend(header_lines)
        lines.append("-" * width)
        lines.extend(transcript_lines)
        lines.append("-" * width)
        lines.extend(composer_lines)
        lines.extend(overlay_lines)
        return "\n".join(lines[:height])

    def draw(self) -> None:
        self.terminal.clear_screen()
        self.terminal.write(self.render() + "\n")

    def invalidate(self) -> None:
        if self.header is not None:
            self.header.invalidate()
        if self.transcript is not None:
            self.transcript.invalidate()
        if self.composer is not None:
            self.composer.invalidate()
        if self.overlay is not None:
            self.overlay.invalidate()

    def run(self) -> int:
        self.draw()
        if not self._terminal_is_interactive():
            return 0

        def on_input(token: str) -> None:
            result = self.handle_key(token)
            if result.refresh:
                self.draw()
            if result.message:
                self.terminal.write(result.message + "\n")
            if result.exit_requested:
                self.stop()

        def on_resize() -> None:
            self.draw()

        self.terminal.hide_cursor()
        self.terminal.start(on_input=on_input, on_resize=on_resize)
        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(0.1)
        finally:
            self.terminal.show_cursor()
            self.terminal.stop()
        return 0

    def stop(self) -> None:
        self._stop_event.set()

    def _terminal_is_interactive(self) -> bool:
        try:
            return bool(getattr(self.terminal, "is_interactive", lambda: True)())
        except Exception:
            return True

    def push_overlay(self, title: str, lines: list[str]) -> None:
        self.state.overlays.append(TuiOverlay(title=title, lines=lines))
        self.invalidate()

    def clear_overlays(self) -> None:
        self.state.overlays.clear()
        self.invalidate()

    def handle_key(self, token: str) -> TuiCommandResult:
        if matches_key(token, Key.enter):
            return self._submit_buffer()
        if matches_key(token, Key.backspace):
            self.state.input_buffer = self.state.input_buffer[:-1]
            return TuiCommandResult(action="backspace", message="", refresh=True)
        if matches_key(token, Key.escape):
            self.clear_overlays()
            self.state.status = "overlay cleared"
            return TuiCommandResult(action="escape", message="", refresh=True)
        if matches_key(token, Key.tab):
            self._show_completion_overlay()
            return TuiCommandResult(action="tab", message="", refresh=True)
        if matches_key(token, Key.ctrl("l")):
            self.clear_overlays()
            self.state.status = "screen refreshed"
            self.invalidate()
            return TuiCommandResult(action="refresh", message="", refresh=True)
        if matches_key(token, Key.up):
            self._history_up()
            self.invalidate()
            return TuiCommandResult(action="history_up", message="", refresh=True)
        if matches_key(token, Key.down):
            self._history_down()
            self.invalidate()
            return TuiCommandResult(action="history_down", message="", refresh=True)
        if token in {"ctrl+c", "\x03"}:
            self.state.status = "shutdown requested"
            return TuiCommandResult(action="quit", message="bye", exit_requested=True)
        if token in {"enter", "tab", "escape", "backspace", "paste_start", "paste_end"}:
            return TuiCommandResult(action="noop", message="", refresh=False)
        if token and not token.startswith("ctrl+") and token not in {"up", "down", "left", "right"}:
            self.state.input_buffer += token
            self.invalidate()
            return TuiCommandResult(action="insert", message="", refresh=True)
        return TuiCommandResult(action="noop", message="", refresh=False)

    def handle_line(self, line: str) -> TuiCommandResult:
        self.state.input_buffer = line
        return self._submit_buffer()

    def _submit_buffer(self) -> TuiCommandResult:
        text = self.state.input_buffer.strip()
        self.state.input_buffer = ""
        self.invalidate()
        if not text:
            return TuiCommandResult(action="noop", message="", refresh=True)
        self.state.history.append(text)
        self.state.history_index = len(self.state.history)
        if text in {"/quit", "/exit"}:
            self.state.status = "shutdown requested"
            return TuiCommandResult(action="quit", message="bye", exit_requested=True)
        if text in {"/help", "help"}:
            self.push_overlay(
                "Help",
                [
                    "/describe  show environment snapshot",
                    "/schemas   list registered schemas",
                    "/validate <schema> <json>",
                    "/reload    reload settings/session/resources",
                    "/session   show recent session entries",
                    "/quit      exit interactive mode",
                ],
            )
            self.state.status = "help opened"
            self.invalidate()
            return TuiCommandResult(action="help", message="help overlay opened")
        if text in {"/describe", "describe"}:
            self.push_overlay("Snapshot", [json.dumps(self.env.snapshot(), ensure_ascii=False, indent=2)])
            self.state.status = "snapshot refreshed"
            self.invalidate()
            return TuiCommandResult(action="describe", message="snapshot refreshed")
        if text in {"/schemas", "schemas"}:
            names = self.env.schema_names()
            self.push_overlay("Schemas", names if names else ["(none)"])
            self.state.status = "schemas listed"
            self.invalidate()
            return TuiCommandResult(action="schemas", message="schemas listed")
        if text.startswith("/validate ") or text.startswith("validate "):
            schema_name, json_text = self._split_validate_command(text)
            if not schema_name:
                self.state.status = "validate command malformed"
                return TuiCommandResult(action="validate", message="usage: /validate <schema> <json>")
            try:
                payload = json.loads(json_text)
                self.env.validate_schema(schema_name, payload)
                self.push_overlay("Validate", [f"{schema_name}: ok"])
                self.state.status = f"validated {schema_name}"
                self.invalidate()
                return TuiCommandResult(action="validate", message=f"{schema_name}: ok")
            except Exception as exc:
                self.push_overlay("Validate", [f"{schema_name}: error", str(exc)])
                self.state.status = f"validation failed for {schema_name}"
                self.invalidate()
                return TuiCommandResult(action="validate", message=str(exc), payload={"error": str(exc)})
        if text in {"/reload", "reload"}:
            self.env.reload()
            self.push_overlay("Reload", ["environment reloaded"])
            self.state.status = "reloaded"
            self.invalidate()
            return TuiCommandResult(action="reload", message="environment reloaded")
        if text in {"/session", "session"}:
            self.push_overlay("Session", self._session_overlay_lines())
            self.state.status = "session overview"
            self.invalidate()
            return TuiCommandResult(action="session", message="session overview")

        self.env.sessions.append_message(UserMessage(content=text))
        self.state.status = f"queued message ({len(text)} chars)"
        self.invalidate()
        return TuiCommandResult(action="message", message="message recorded")

    def _split_validate_command(self, text: str) -> tuple[str | None, str]:
        parts = text.split(" ", 2)
        if len(parts) < 3:
            return None, ""
        if parts[0] in {"/validate", "validate"}:
            return parts[1], parts[2]
        return None, ""

    def _session_overlay_lines(self) -> list[str]:
        header = self.env.sessions.get_header()
        lines = [
            f"id: {header.id if header else 'n/a'}",
            f"cwd: {header.cwd if header else 'n/a'}",
            f"messages: {len(self.env.sessions.get_entries())}",
            f"leaf: {self.env.sessions.get_leaf_id() or 'none'}",
        ]
        recent = self.env.sessions.get_entries()[-5:]
        if recent:
            lines.append("recent:")
            lines.extend(f"  - {format_entry(entry)}" for entry in recent)
        return lines

    def _show_completion_overlay(self) -> None:
        suggestions = self.env.schema_names()
        self.push_overlay("Completion", suggestions if suggestions else ["(no schema suggestions)"])
        self.state.status = "completion opened"

    def _history_up(self) -> None:
        if not self.state.history:
            return
        self.state.history_index = max(0, self.state.history_index - 1)
        self.state.input_buffer = self.state.history[self.state.history_index]

    def _history_down(self) -> None:
        if not self.state.history:
            return
        self.state.history_index = min(len(self.state.history), self.state.history_index + 1)
        if self.state.history_index >= len(self.state.history):
            self.state.input_buffer = ""
        else:
            self.state.input_buffer = self.state.history[self.state.history_index]
