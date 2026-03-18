"""Print mode skeleton."""

from __future__ import annotations

import json
from dataclasses import dataclass
import sys

from .environment import build_mode_environment
from .shared import ModeExitCode, ModeInvocation, parse_invocation


@dataclass(slots=True)
class PrintModeOptions:
    cwd: str | None = None
    config_dir: str | None = None
    session_dir: str | None = None
    json_output: bool = False


class PrintMode:
    def __init__(self, options: PrintModeOptions | None = None) -> None:
        self.options = options or PrintModeOptions()

    def run(self) -> int:
        invocation = ModeInvocation(
            mode="print",
            cwd=self.options.cwd,
            config_dir=self.options.config_dir,
            session_dir=self.options.session_dir,
            json_output=self.options.json_output,
        )
        env = build_mode_environment(invocation)
        payload = {
            "mode": "print",
            "snapshot": env.snapshot(),
            "summary": env.describe(),
        }
        if self.options.json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("pimono print mode bootstrap")
            summary = payload["summary"]
            print(f"cwd: {summary['cwd']}")
            print(f"session: {summary['session_id']} ({summary['session_messages']} messages)")
            print(f"model: {summary['default_provider']}/{summary['default_model']}")
            print(f"schemas: {', '.join(summary['schemas'])}")
        return int(ModeExitCode.OK)


def main(argv: list[str] | None = None) -> int:
    invocation = parse_invocation(argv, fixed_mode="print")
    return PrintMode(
        PrintModeOptions(
            cwd=invocation.cwd,
            config_dir=invocation.config_dir,
            session_dir=invocation.session_dir,
            json_output=invocation.json_output,
        )
    ).run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
