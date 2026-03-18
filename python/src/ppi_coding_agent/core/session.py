"""Session tree and JSONL persistence models."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ppi_ai import AssistantMessage, ImageContent, Message, TextContent, ThinkingContent, ToolCall, ToolResultMessage, UserMessage

from .types import (
    ReadonlySessionManager,
    SessionBranchSummaryEntry,
    SessionCompactionEntry,
    SessionContext,
    SessionCustomEntry,
    SessionCustomMessageEntry,
    SessionEntry,
    SessionEntryKind,
    SessionHeader,
    SessionInfo,
    SessionInfoEntry,
    SessionLabelEntry,
    SessionManager,
    SessionMessageEntry,
    SessionStats,
    SessionTreeNode,
)

from .helpers import (
    new_id as _new_id,
    now_iso as _now_iso,
    latest_session_path as _latest_session_path,
    session_path as _session_path,
)
from .reader import build_session_context as _build_session_context, get_session_info as _get_session_info, get_stats as _get_stats, infer_session_name as _infer_session_name, load_session as _load_session
from .tree import (
    branch as _branch,
    branch_with_summary as _branch_with_summary,
    create_branched_session as _create_branched_session,
    get_branch as _get_branch,
    get_children as _get_children,
    get_entry as _get_entry,
    get_header as _get_header,
    get_leaf_entry as _get_leaf_entry,
    get_leaf_id as _get_leaf_id,
    get_tree as _get_tree,
    reset_leaf as _reset_leaf,
)
from .writer import (
    append_branch_summary as _append_branch_summary,
    append_compaction as _append_compaction,
    append_entry as _append_entry,
    append_label_change as _append_label_change,
    append_message as _append_message,
    append_session_info as _append_session_info,
    close as _close,
    flush as _flush,
)


@dataclass(slots=True)
class InMemorySessionManager:
    cwd: str = "."
    session_dir: str | None = None
    path: Path | None = None
    autosave: bool = False
    header: SessionHeader | None = None
    entries: list[SessionEntry] = field(default_factory=list)
    entry_index: dict[str, SessionEntry] = field(default_factory=dict)
    parent_index: dict[str, list[str]] = field(default_factory=dict)
    leaf_id: str | None = None
    session_name: str | None = None
    closed: bool = False

    @classmethod
    def create(cls, cwd: str, session_dir: str | None = None) -> "InMemorySessionManager":
        manager = cls(cwd=cwd, session_dir=session_dir)
        manager.header = SessionHeader(id=_new_id("session"), timestamp=_now_iso(), cwd=cwd)
        manager.path = _session_path(cwd, session_dir, manager.header.id)
        manager.autosave = manager.path is not None
        _flush(manager)
        return manager

    @classmethod
    def open(cls, path: str, session_dir: str | None = None) -> "InMemorySessionManager":
        manager = cls(cwd=str(Path(path).parent), session_dir=session_dir, path=Path(path), autosave=True)
        manager.reload()
        if manager.header is None:
            manager.header = SessionHeader(id=_new_id("session"), timestamp=_now_iso(), cwd=manager.cwd)
        return manager

    @classmethod
    def continue_recent(cls, cwd: str, session_dir: str | None = None) -> "InMemorySessionManager":
        latest = _latest_session_path(cwd, session_dir)
        if latest is not None:
            return cls.open(str(latest), session_dir=session_dir)
        return cls.create(cwd, session_dir=session_dir)

    @classmethod
    def fork_from(
        cls, source_path: str, target_cwd: str, session_dir: str | None = None
    ) -> "InMemorySessionManager":
        source = cls.open(source_path, session_dir=session_dir)
        manager = cls.create(target_cwd, session_dir=session_dir)
        manager.entries = list(source.entries)
        manager.entry_index = dict(source.entry_index)
        manager.parent_index = {key: list(value) for key, value in source.parent_index.items()}
        manager.leaf_id = source.leaf_id
        manager.session_name = source.session_name
        manager.append_session_info(f"forked-from:{source_path}")
        return manager

    @classmethod
    def in_memory(cls, cwd: str = ".") -> "InMemorySessionManager":
        manager = cls(cwd=cwd, session_dir=None, path=None, autosave=False)
        manager.header = SessionHeader(id=_new_id("session"), timestamp=_now_iso(), cwd=cwd)
        return manager

    def append_entry(self, entry: SessionEntry) -> None:
        _append_entry(self, entry)

    def append_message(self, message: Message | AssistantMessage) -> None:
        _append_message(self, message)

    def append_branch_summary(self, from_id: str, summary: str, details: dict[str, Any] | None = None) -> None:
        _append_branch_summary(self, from_id, summary, details)

    def append_compaction(self, summary: str, first_kept_entry_id: str, tokens_before: int) -> None:
        _append_compaction(self, summary, first_kept_entry_id, tokens_before)

    def append_session_info(self, name: str) -> None:
        _append_session_info(self, name)

    def append_label_change(self, target_id: str, label: str | None) -> None:
        _append_label_change(self, target_id, label)

    def get_entries(self) -> list[SessionEntry]:
        return list(self.entries)

    def build_context(self, leaf_id: str | None = None) -> SessionContext:
        return _build_session_context(self, leaf_id)

    def get_tree(self) -> list[SessionTreeNode]:
        return _get_tree(self)

    def get_branch(self, from_id: str | None = None) -> list[SessionEntry]:
        return _get_branch(self, from_id)

    def branch(self, branch_from_id: str | None = None) -> str:
        return _branch(self, branch_from_id)

    def branch_with_summary(self, branch_from_id: str | None, summary: str, details: Any | None = None) -> str:
        return _branch_with_summary(self, branch_from_id, summary, details)

    def reset_leaf(self, new_leaf_id: str | None) -> None:
        _reset_leaf(self, new_leaf_id)

    def create_branched_session(self, branch_from_id: str | None = None) -> "InMemorySessionManager":
        return _create_branched_session(self, branch_from_id)

    def get_header(self) -> SessionHeader | None:
        return _get_header(self)

    def get_leaf_id(self) -> str | None:
        return _get_leaf_id(self)

    def get_leaf_entry(self) -> SessionEntry | None:
        return _get_leaf_entry(self)

    def get_entry(self, entry_id: str) -> SessionEntry | None:
        return _get_entry(self, entry_id)

    def get_children(self, parent_id: str) -> list[SessionEntry]:
        return _get_children(self, parent_id)

    def set_session_name(self, name: str) -> None:
        self.session_name = name

    def get_session_name(self) -> str | None:
        return self.session_name

    def get_session_info(self) -> SessionInfo | None:
        return _get_session_info(self)

    def get_stats(self) -> SessionStats:
        return _get_stats(self)

    def reload(self) -> None:
        _load_session(self)

    def flush(self) -> None:
        _flush(self)

    def close(self) -> None:
        _close(self)
