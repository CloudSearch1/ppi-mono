"""CLI bootstrap helpers for the coding-agent layer."""

from __future__ import annotations

from dataclasses import dataclass

from ..modes import InteractiveMode, InteractiveModeOptions, ModeExitCode, PrintMode, PrintModeOptions, RpcMode, RpcModeOptions, ModeInvocation, parse_invocation


@dataclass(slots=True)
class CliDispatchResult:
    invocation: ModeInvocation
    exit_code: int


def dispatch_invocation(invocation: ModeInvocation) -> int:
    if invocation.mode == "interactive":
        return InteractiveMode(
            InteractiveModeOptions(
                cwd=invocation.cwd,
                config_dir=invocation.config_dir,
                session_dir=invocation.session_dir,
                session_id=invocation.session_id,
                theme=invocation.theme,
            )
        ).run()
    if invocation.mode == "print":
        return PrintMode(
            PrintModeOptions(
                cwd=invocation.cwd,
                config_dir=invocation.config_dir,
                session_dir=invocation.session_dir,
                json_output=invocation.json_output,
            )
        ).run()
    if invocation.mode == "rpc":
        return RpcMode(
            RpcModeOptions(
                cwd=invocation.cwd,
                config_dir=invocation.config_dir,
                session_dir=invocation.session_dir,
                input_fd=invocation.input_fd,
                output_fd=invocation.output_fd,
            )
        ).run()
    return int(ModeExitCode.INVALID_ARGUMENTS)


def run_cli(argv: list[str] | None = None) -> CliDispatchResult:
    invocation = parse_invocation(argv)
    return CliDispatchResult(invocation=invocation, exit_code=dispatch_invocation(invocation))
