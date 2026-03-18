"""Session-related protocol and dataclass definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeAlias

from ppi_ai import AssistantMessage, Message


@dataclass(slots=True)
class SessionHeader:
    type: Literal["session"] = "session"
    version: int = 1
    id: str = ""
    timestamp: str = ""
    cwd: str = ""
    parent_session: str | None = None


@dataclass(slots=True, kw_only=True)
class SessionEntry:
    type: str
    id: str
    parent_id: str | None
    timestamp: str


SessionEntryKind: TypeAlias = Literal[
    "message",
    "thinking_level_change",
    "model_change",
    "compaction",
    "branch_summary",
    "custom",
    "custom_message",
    "label",
    "session_info",
]


@dataclass(slots=True, kw_only=True)
class SessionMessageEntry(SessionEntry):
    type: SessionEntryKind = "message"
    message: Message | AssistantMessage | None = None


@dataclass(slots=True, kw_only=True)
class SessionCompactionEntry(SessionEntry):
    type: SessionEntryKind = "compaction"
    summary: str = ""
    first_kept_entry_id: str = ""
    tokens_before: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class SessionBranchSummaryEntry(SessionEntry):
    type: SessionEntryKind = "branch_summary"
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class SessionCustomEntry(SessionEntry):
    type: SessionEntryKind = "custom"
    custom_type: str = ""
    data: Any = None


@dataclass(slots=True, kw_only=True)
class SessionCustomMessageEntry(SessionEntry):
    type: SessionEntryKind = "custom_message"
    custom_type: str = ""
    content: Any = None
    display: bool = True
    details: Any = None


@dataclass(slots=True, kw_only=True)
class SessionLabelEntry(SessionEntry):
    type: SessionEntryKind = "label"
    label: str | None = None


@dataclass(slots=True, kw_only=True)
class SessionInfoEntry(SessionEntry):
    type: SessionEntryKind = "session_info"
    name: str = ""


@dataclass(slots=True)
class SessionTreeNode:
    entry: SessionEntry
    children: list["SessionTreeNode"] = field(default_factory=list)
    label: str | None = None


@dataclass(slots=True)
class SessionContext:
    messages: list[Message] = field(default_factory=list)
    thinking_level: str = "off"
    model: dict[str, str] | None = None
    session_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SessionStats:
    message_count: int = 0
    tool_call_count: int = 0
    compaction_count: int = 0
    branch_count: int = 0


@dataclass(slots=True)
class SessionInfo:
    path: str
    id: str
    cwd: str = ""
    name: str | None = None
    parent_session_path: str | None = None
    created: str = ""
    modified: str = ""
    message_count: int = 0
    first_message: str = ""
    all_messages_text: str = ""


class SessionManager(Protocol):
    @classmethod
    def create(cls, cwd: str, session_dir: str | None = None) -> "SessionManager":
        ...

    @classmethod
    def open(cls, path: str, session_dir: str | None = None) -> "SessionManager":
        ...

    @classmethod
    def continue_recent(cls, cwd: str, session_dir: str | None = None) -> "SessionManager":
        ...

    @classmethod
    def fork_from(
        cls, source_path: str, target_cwd: str, session_dir: str | None = None
    ) -> "SessionManager":
        ...

    @classmethod
    def in_memory(cls, cwd: str = ".") -> "SessionManager":
        ...

    def append_entry(self, entry: SessionEntry) -> None:
        ...

    def append_message(self, message: Message | AssistantMessage) -> None:
        ...

    def append_branch_summary(self, from_id: str, summary: str, details: dict[str, Any] | None = None) -> None:
        ...

    def append_compaction(self, summary: str, first_kept_entry_id: str, tokens_before: int) -> None:
        ...

    def append_session_info(self, name: str) -> None:
        ...

    def append_label_change(self, target_id: str, label: str | None) -> None:
        ...

    def get_entries(self) -> list[SessionEntry]:
        ...

    def build_context(self, leaf_id: str | None = None) -> SessionContext:
        ...

    def get_tree(self) -> list[SessionTreeNode]:
        ...

    def get_branch(self, from_id: str | None = None) -> list[SessionEntry]:
        ...

    def branch(self, branch_from_id: str | None = None) -> str:
        ...

    def branch_with_summary(self, branch_from_id: str | None, summary: str, details: Any | None = None) -> str:
        ...

    def reset_leaf(self, new_leaf_id: str | None) -> None:
        ...

    def create_branched_session(self, branch_from_id: str | None = None) -> "SessionManager":
        ...

    def get_header(self) -> SessionHeader | None:
        ...

    def get_leaf_id(self) -> str | None:
        ...

    def get_leaf_entry(self) -> SessionEntry | None:
        ...

    def get_entry(self, entry_id: str) -> SessionEntry | None:
        ...

    def get_children(self, parent_id: str) -> list[SessionEntry]:
        ...

    def set_session_name(self, name: str) -> None:
        ...

    def get_session_name(self) -> str | None:
        ...

    def get_session_info(self) -> SessionInfo | None:
        ...

    def get_stats(self) -> SessionStats:
        ...

    def reload(self) -> None:
        ...

    def flush(self) -> None:
        ...

    def close(self) -> None:
        ...


ReadonlySessionManager = SessionManager


__all__ = [
    "ReadonlySessionManager",
    "SessionBranchSummaryEntry",
    "SessionCompactionEntry",
    "SessionContext",
    "SessionCustomEntry",
    "SessionCustomMessageEntry",
    "SessionEntry",
    "SessionEntryKind",
    "SessionHeader",
    "SessionInfo",
    "SessionInfoEntry",
    "SessionLabelEntry",
    "SessionManager",
    "SessionMessageEntry",
    "SessionStats",
    "SessionTreeNode",
]
