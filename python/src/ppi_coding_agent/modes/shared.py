"""Shared mode parsing and exit-code conventions.

This module defines the stable command-line contract for the three runtime
shells:

- ``interactive``: human-driven TUI shell
- ``print``: one-shot text / JSON output shell
- ``rpc``: JSONL command bridge for host processes

The parsing layer is intentionally small and only carries cross-mode arguments.
Mode-specific business logic belongs in the concrete mode classes.

Exit code contract:

- ``0``: success
- ``1``: runtime failure
- ``2``: invalid arguments or unsupported mode
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import IntEnum
from typing import Literal


ModeName = Literal["interactive", "print", "rpc"]


class ModeExitCode(IntEnum):
    OK = 0
    ERROR = 1
    INVALID_ARGUMENTS = 2


@dataclass(slots=True)
class ModeInvocation:
    mode: ModeName
    cwd: str | None = None
    config_dir: str | None = None
    session_dir: str | None = None
    session_id: str | None = None
    theme: str | None = None
    json_output: bool = False
    input_fd: int | None = None
    output_fd: int | None = None


def build_parser(*, default_mode: ModeName = "interactive", include_mode: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pimono",
        description="Python rewrite bootstrap for pi-mono.",
    )
    if include_mode:
        parser.add_argument(
            "--mode",
            choices=("interactive", "print", "rpc"),
            default=default_mode,
            help="Select the runtime shell to preview.",
        )
    parser.add_argument("--cwd", default=None, help="Override the working directory used by the runtime.")
    parser.add_argument(
        "--config-dir",
        default=None,
        help="Override the config directory used for settings, models, resources and extensions.",
    )
    parser.add_argument("--session-dir", default=None, help="Override the session directory.")
    parser.add_argument("--session-id", default=None, help="Preview a specific session id.")
    parser.add_argument("--theme", default=None, help="Preview an interactive theme name.")
    parser.add_argument("--json", action="store_true", help="Preview print mode with JSON output.")
    parser.add_argument("--input-fd", type=int, default=None, help="Preview RPC input fd.")
    parser.add_argument("--output-fd", type=int, default=None, help="Preview RPC output fd.")
    return parser


def parse_invocation(
    argv: list[str] | None = None,
    *,
    default_mode: ModeName = "interactive",
    fixed_mode: ModeName | None = None,
) -> ModeInvocation:
    args = build_parser(default_mode=default_mode).parse_args(argv)
    mode = fixed_mode or args.mode
    return ModeInvocation(
        mode=mode,
        cwd=args.cwd,
        config_dir=args.config_dir,
        session_dir=args.session_dir,
        session_id=args.session_id,
        theme=args.theme,
        json_output=bool(args.json),
        input_fd=args.input_fd,
        output_fd=args.output_fd,
    )
