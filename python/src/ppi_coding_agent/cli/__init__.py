"""CLI entry points for the coding-agent layer."""

from .main import main
from .bootstrap import CliDispatchResult, dispatch_invocation, run_cli

__all__ = ["CliDispatchResult", "dispatch_invocation", "main", "run_cli"]
