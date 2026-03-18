"""RPC mode skeleton."""

from __future__ import annotations

import json
from dataclasses import dataclass
import os
import sys

from .environment import build_mode_environment
from .shared import ModeExitCode, ModeInvocation, parse_invocation


@dataclass(slots=True)
class RpcModeOptions:
    cwd: str | None = None
    config_dir: str | None = None
    session_dir: str | None = None
    input_fd: int | None = None
    output_fd: int | None = None


class RpcMode:
    def __init__(self, options: RpcModeOptions | None = None) -> None:
        self.options = options or RpcModeOptions()

    def run(self) -> int:
        invocation = ModeInvocation(
            mode="rpc",
            cwd=self.options.cwd,
            config_dir=self.options.config_dir,
            session_dir=self.options.session_dir,
            input_fd=self.options.input_fd,
            output_fd=self.options.output_fd,
        )
        env = build_mode_environment(invocation)
        self._run_rpc_loop(env)
        return int(ModeExitCode.OK)

    def _run_rpc_loop(self, env) -> None:
        reader = self._open_reader()
        writer = self._open_writer()
        self._write_line(writer, {"type": "rpc_ready", "summary": env.describe()})
        for raw in reader:
            raw = raw.strip()
            if not raw:
                continue
            try:
                command = json.loads(raw)
            except Exception as exc:
                self._write_line(writer, {"type": "error", "error": f"invalid json: {exc}"})
                continue
            response = self._handle_command(env, command)
            self._write_line(writer, response)
            if response.get("shutdown"):
                break

    def _handle_command(self, env, command: dict[str, object]) -> dict[str, object]:
        command_type = str(command.get("type") or command.get("command") or "")
        if command_type in {"describe", "get_state"}:
            return {"type": "response", "command": command_type, "data": env.snapshot()}
        if command_type == "list_schemas":
            return {"type": "response", "command": command_type, "data": env.schema_names()}
        if command_type == "reload":
            env.reload()
            return {"type": "response", "command": command_type, "data": env.describe()}
        if command_type == "validate_schema":
            schema_name = str(command.get("schema") or "")
            payload = command.get("data")
            try:
                env.validate_schema(schema_name, payload)
                return {"type": "response", "command": command_type, "ok": True}
            except Exception as exc:
                return {"type": "response", "command": command_type, "ok": False, "error": str(exc)}
        if command_type in {"shutdown", "exit", "quit"}:
            return {"type": "response", "command": command_type, "shutdown": True, "ok": True}
        return {"type": "error", "error": f"unknown command: {command_type}"}

    def _open_reader(self):
        if self.options.input_fd is not None:
            return os.fdopen(self.options.input_fd, "r", encoding="utf-8", closefd=False)
        return sys.stdin

    def _open_writer(self):
        if self.options.output_fd is not None:
            return os.fdopen(self.options.output_fd, "w", encoding="utf-8", closefd=False)
        return sys.stdout

    def _write_line(self, writer, payload: dict[str, object]) -> None:
        line = json.dumps(payload, ensure_ascii=False)
        writer.write(line + "\n")
        writer.flush()


def main(argv: list[str] | None = None) -> int:
    invocation = parse_invocation(argv, fixed_mode="rpc")
    return RpcMode(
        RpcModeOptions(
            cwd=invocation.cwd,
            config_dir=invocation.config_dir,
            session_dir=invocation.session_dir,
            input_fd=invocation.input_fd,
            output_fd=invocation.output_fd,
        )
    ).run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
