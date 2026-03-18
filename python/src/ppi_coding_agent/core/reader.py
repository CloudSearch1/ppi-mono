"""Session reader helpers."""

from __future__ import annotations

from typing import Any

from ppi_ai import AssistantMessage, Message

from .helpers import load_session_jsonl
from .session_types import SessionBranchSummaryEntry, SessionCompactionEntry, SessionContext, SessionCustomEntry, SessionInfo, SessionInfoEntry, SessionMessageEntry, SessionStats


def load_session(manager: Any) -> None:
    if manager.path is None or not manager.path.exists():
        return None
    header, entries = load_session_jsonl(manager.path)
    manager.header = header
    manager.entries = entries
    manager.entry_index = {entry.id: entry for entry in entries}
    manager.parent_index = {}
    for entry in entries:
        if entry.parent_id:
            manager.parent_index.setdefault(entry.parent_id, []).append(entry.id)
    manager.leaf_id = entries[-1].id if entries else None
    if manager.header is not None:
        manager.cwd = manager.header.cwd or manager.cwd
    manager.session_name = infer_session_name(manager)


def infer_session_name(manager: Any) -> str | None:
    if getattr(manager, "session_name", None):
        return manager.session_name
    for entry in reversed(getattr(manager, "entries", [])):
        if isinstance(entry, SessionInfoEntry):
            return entry.name
    return None


def build_session_context(manager: Any, leaf_id: str | None = None) -> SessionContext:
    context = SessionContext(thinking_level="off", session_name=manager.session_name)
    if leaf_id is None:
        selected_entries = manager.entries
    else:
        selected_entries = []
        for entry in manager.entries:
            selected_entries.append(entry)
            if entry.id == leaf_id:
                break
    for entry in selected_entries:
        if isinstance(entry, SessionMessageEntry) and entry.message is not None:
            context.messages.append(entry.message)
        elif isinstance(entry, SessionInfoEntry):
            context.session_name = entry.name
        elif isinstance(entry, SessionCustomEntry):
            context.metadata[entry.custom_type] = entry.data
    return context


def get_session_info(manager: Any) -> SessionInfo | None:
    if manager.header is None:
        return None
    first_message = ""
    all_text: list[str] = []
    message_count = 0
    for entry in manager.entries:
        if isinstance(entry, SessionMessageEntry) and entry.message is not None:
            message_count += 1
            if not first_message and hasattr(entry.message, "content"):
                first_message = str(getattr(entry.message, "content", ""))
            all_text.append(str(getattr(entry.message, "content", "")))
    return SessionInfo(
        path=manager.session_dir or "",
        id=manager.header.id,
        cwd=manager.header.cwd,
        name=manager.session_name,
        parent_session_path=manager.header.parent_session,
        created=manager.header.timestamp,
        modified=manager.entries[-1].timestamp if manager.entries else manager.header.timestamp,
        message_count=message_count,
        first_message=first_message,
        all_messages_text="\n".join(all_text),
    )


def get_stats(manager: Any) -> SessionStats:
    stats = SessionStats()
    for entry in manager.entries:
        if isinstance(entry, SessionMessageEntry):
            stats.message_count += 1
            if hasattr(entry.message, "tool_calls"):
                stats.tool_call_count += len(getattr(entry.message, "tool_calls", []) or [])
        elif isinstance(entry, SessionCompactionEntry):
            stats.compaction_count += 1
        elif isinstance(entry, SessionBranchSummaryEntry):
            stats.branch_count += 1
    return stats
