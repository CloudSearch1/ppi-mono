"""CLI bootstrap for the Python rewrite."""

from __future__ import annotations

import sys

from .bootstrap import run_cli

def main(argv: list[str] | None = None) -> int:
    """Minimal runnable CLI entry point."""
    return run_cli(argv).exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
