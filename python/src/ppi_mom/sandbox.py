"""Sandbox execution contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class SandboxConfig:
    type: str
    container: str | None = None


@dataclass(slots=True)
class ExecResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""


class Executor(Protocol):
    def exec(self, command: str) -> ExecResult:
        ...

    def get_workspace_path(self, host_path: str) -> str:
        ...
