"""Interactive terminal mode skeleton."""

from __future__ import annotations

from dataclasses import dataclass
import sys

from .environment import build_mode_environment
from .shared import ModeExitCode, ModeInvocation, parse_invocation
from .tui import InteractiveTuiApp


@dataclass(slots=True)
class InteractiveModeOptions:
    cwd: str | None = None
    config_dir: str | None = None
    session_dir: str | None = None
    session_id: str | None = None
    theme: str | None = None


class InteractiveMode:
    def __init__(self, options: InteractiveModeOptions | None = None) -> None:
        self.options = options or InteractiveModeOptions()

    def run(self) -> int:
        invocation = ModeInvocation(
            mode="interactive",
            cwd=self.options.cwd,
            config_dir=self.options.config_dir,
            session_dir=self.options.session_dir,
            session_id=self.options.session_id,
            theme=self.options.theme,
        )
        env = build_mode_environment(invocation)
        app = InteractiveTuiApp(env)
        return int(app.run())


def main(argv: list[str] | None = None) -> int:
    invocation = parse_invocation(argv, fixed_mode="interactive")
    return InteractiveMode(
        InteractiveModeOptions(
            cwd=invocation.cwd,
            config_dir=invocation.config_dir,
            session_dir=invocation.session_dir,
            session_id=invocation.session_id,
            theme=invocation.theme,
        )
    ).run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
