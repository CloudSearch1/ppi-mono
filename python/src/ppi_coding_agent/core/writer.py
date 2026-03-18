"""Session writer helpers."""

from __future__ import annotations

from typing import Any

from .helpers import entry_to_record, write_session_jsonl
from .session_types import SessionBranchSummaryEntry, SessionCompactionEntry, SessionCustomMessageEntry, SessionEntry, SessionInfoEntry, SessionLabelEntry, SessionMessageEntry


def append_entry(manager: Any, entry: SessionEntry) -> None:
    if manager.closed:
        raise RuntimeError("session manager is closed")
    manager.entries.append(entry)
    manager.entry_index[entry.id] = entry
    if entry.parent_id:
        manager.parent_index.setdefault(entry.parent_id, []).append(entry.id)
    manager.leaf_id = entry.id
    if manager.autosave:
        flush(manager)


def append_message(manager: Any, message: Any) -> None:
    from .helpers import new_id, now_iso
    from .session_types import SessionMessageEntry

    append_entry(
        manager,
        SessionMessageEntry(
            id=new_id("message"),
            parent_id=manager.leaf_id,
            timestamp=now_iso(),
            message=message,
        ),
    )


def append_branch_summary(manager: Any, from_id: str, summary: str, details: dict[str, Any] | None = None) -> None:
    from .helpers import new_id, now_iso

    append_entry(
        manager,
        SessionBranchSummaryEntry(
            id=new_id("branch"),
            parent_id=from_id,
            timestamp=now_iso(),
            summary=summary,
            details=details or {},
        ),
    )


def append_compaction(manager: Any, summary: str, first_kept_entry_id: str, tokens_before: int) -> None:
    from .helpers import new_id, now_iso

    append_entry(
        manager,
        SessionCompactionEntry(
            id=new_id("compaction"),
            parent_id=manager.leaf_id,
            timestamp=now_iso(),
            summary=summary,
            first_kept_entry_id=first_kept_entry_id,
            tokens_before=tokens_before,
        ),
    )


def append_session_info(manager: Any, name: str) -> None:
    from .helpers import new_id, now_iso

    manager.session_name = name
    append_entry(
        manager,
        SessionInfoEntry(
            id=new_id("session-info"),
            parent_id=manager.leaf_id,
            timestamp=now_iso(),
            name=name,
        ),
    )


def append_label_change(manager: Any, target_id: str, label: str | None) -> None:
    from .helpers import new_id, now_iso

    append_entry(
        manager,
        SessionLabelEntry(
            id=new_id("label"),
            parent_id=target_id,
            timestamp=now_iso(),
            label=label,
        ),
    )


def flush(manager: Any) -> None:
    if manager.path is None:
        return None
    manager.path.parent.mkdir(parents=True, exist_ok=True)
    write_session_jsonl(manager.path, manager.header, manager.entries)


def close(manager: Any) -> None:
    flush(manager)
    manager.closed = True
