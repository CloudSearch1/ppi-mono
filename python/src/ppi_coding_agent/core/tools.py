"""Built-in tool definitions and a local tool runner."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ppi_agent_core import AgentToolResult
from ppi_ai import TextContent

from .types import ToolDefinition, ToolExecutionContext, ToolKind, ToolRegistry, ToolRunner


def create_default_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="read",
            label="Read",
            description="Read file contents",
            kind="read",
        ),
        ToolDefinition(
            name="write",
            label="Write",
            description="Create or overwrite files",
            kind="write",
        ),
        ToolDefinition(
            name="edit",
            label="Edit",
            description="Make surgical edits to files",
            kind="edit",
        ),
        ToolDefinition(
            name="bash",
            label="Bash",
            description="Execute shell commands",
            kind="bash",
        ),
    ]


@dataclass(slots=True)
class LocalToolRunner:
    cwd: str = "."

    def execute(
        self,
        tool_call_id: str,
        args: dict[str, Any],
        context: ToolExecutionContext | None = None,
    ) -> Any:
        tool_name = context.tool_name if context else str(args.get("tool", ""))
        workdir = Path((context.cwd if context and context.cwd else self.cwd) or ".")

        if tool_name == "bash":
            command = str(args.get("command") or args.get("text") or "")
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(workdir),
                capture_output=True,
                text=True,
                check=False,
            )
            output = (result.stdout or "") + (result.stderr or "")
            return _tool_result(tool_call_id, tool_name, output, result.returncode == 0)

        if tool_name == "read":
            path = Path(str(args.get("path") or args.get("file") or ""))
            if not path.is_absolute():
                path = workdir / path
            if not path.exists():
                return _tool_result(tool_call_id, tool_name, f"File not found: {path}", False)
            return _tool_result(tool_call_id, tool_name, path.read_text(encoding="utf-8"), True)

        if tool_name == "write":
            path = Path(str(args.get("path") or ""))
            content = str(args.get("content") or args.get("text") or "")
            if not path.is_absolute():
                path = workdir / path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return _tool_result(tool_call_id, tool_name, f"Wrote {path}", True)

        if tool_name == "edit":
            path = Path(str(args.get("path") or ""))
            old = str(args.get("old") or "")
            new = str(args.get("new") or "")
            if not path.is_absolute():
                path = workdir / path
            text = path.read_text(encoding="utf-8")
            if old and old not in text:
                return _tool_result(tool_call_id, tool_name, f"Pattern not found in {path}", False)
            if old:
                text = text.replace(old, new)
            else:
                text = new
            path.write_text(text, encoding="utf-8")
            return _tool_result(tool_call_id, tool_name, f"Edited {path}", True)

        if tool_name == "ls":
            path = Path(str(args.get("path") or "."))
            if not path.is_absolute():
                path = workdir / path
            entries = sorted(p.name for p in path.iterdir()) if path.exists() else []
            return _tool_result(tool_call_id, tool_name, "\n".join(entries), True)

        if tool_name in {"find", "grep"}:
            pattern = str(args.get("pattern") or args.get("query") or "")
            root = Path(str(args.get("path") or "."))
            if not root.is_absolute():
                root = workdir / root
            matches: list[str] = []
            if root.exists():
                for candidate in root.rglob("*"):
                    if candidate.is_file():
                        try:
                            text = candidate.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            continue
                        if pattern in text or pattern in candidate.name:
                            matches.append(str(candidate))
            return _tool_result(tool_call_id, tool_name, "\n".join(matches), True)

        return _tool_result(tool_call_id, tool_name, f"Unsupported tool: {tool_name}", False)


def _tool_result(tool_call_id: str, tool_name: str, text: str, ok: bool) -> Any:
    return AgentToolResult(
        content=[TextContent(text=text)],
        details={"tool_call_id": tool_call_id, "tool_name": tool_name, "ok": ok},
    )
