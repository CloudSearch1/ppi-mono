"""Tool protocol and dataclass definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeAlias


ToolKind: TypeAlias = Literal["read", "write", "edit", "bash", "grep", "find", "ls", "custom"]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    label: str
    description: str
    prompt_snippet: str = ""
    prompt_guidelines: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    kind: ToolKind = "custom"
    enabled: bool = True
    tags: list[str] = field(default_factory=list)
    output_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolExecutionContext:
    tool_name: str
    tool_call_id: str
    cwd: str = ""
    cwd_workspace: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolRunner(Protocol):
    def execute(
        self,
        tool_call_id: str,
        args: dict[str, Any],
        context: ToolExecutionContext | None = None,
    ) -> Any:
        ...


@dataclass(slots=True)
class ToolRegistry:
    tools: dict[str, ToolDefinition] = field(default_factory=dict)

    def register(self, tool: ToolDefinition) -> None:
        self.tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        return self.tools[name]

    def list(self) -> list[ToolDefinition]:
        return list(self.tools.values())


def create_default_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(name="read", label="Read", description="Read file contents", kind="read"),
        ToolDefinition(name="write", label="Write", description="Create or overwrite files", kind="write"),
        ToolDefinition(name="edit", label="Edit", description="Make surgical edits to files", kind="edit"),
        ToolDefinition(name="bash", label="Bash", description="Execute shell commands", kind="bash"),
    ]


__all__ = ["ToolDefinition", "ToolExecutionContext", "ToolKind", "ToolRegistry", "ToolRunner", "create_default_tools"]
