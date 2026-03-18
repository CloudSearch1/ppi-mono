"""Session tree and branch helpers."""

from __future__ import annotations

from typing import Any

from .helpers import latest_session_path, new_id, now_iso, session_path
from .session_types import SessionBranchSummaryEntry, SessionContext, SessionEntry, SessionHeader, SessionInfoEntry, SessionLabelEntry, SessionMessageEntry, SessionTreeNode


def get_tree(manager: Any) -> list[SessionTreeNode]:
    nodes: dict[str, SessionTreeNode] = {}
    roots: list[SessionTreeNode] = []
    for entry in manager.entries:
        nodes[entry.id] = SessionTreeNode(entry=entry)
    for entry in manager.entries:
        node = nodes[entry.id]
        if entry.parent_id and entry.parent_id in nodes:
            nodes[entry.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


def get_branch(manager: Any, from_id: str | None = None) -> list[SessionEntry]:
    if from_id is None:
        return list(manager.entries)
    result: list[SessionEntry] = []
    found = False
    for entry in manager.entries:
        if found:
            result.append(entry)
        if entry.id == from_id:
            found = True
            result.append(entry)
    return result


def branch(manager: Any, branch_from_id: str | None = None) -> str:
    branch_id = new_id("branch")
    from .writer import append_entry

    append_entry(
        manager,
        SessionLabelEntry(
            id=branch_id,
            parent_id=branch_from_id or manager.leaf_id,
            timestamp=now_iso(),
            label=None,
        ),
    )
    return branch_id


def branch_with_summary(manager: Any, branch_from_id: str | None, summary: str, details: Any | None = None) -> str:
    branch_id = new_id("branch")
    from .writer import append_entry

    append_entry(
        manager,
        SessionBranchSummaryEntry(
            id=branch_id,
            parent_id=branch_from_id or manager.leaf_id,
            timestamp=now_iso(),
            summary=summary,
            details=details or {},
        ),
    )
    return branch_id


def reset_leaf(manager: Any, new_leaf_id: str | None) -> None:
    if new_leaf_id is None or new_leaf_id in manager.entry_index:
        manager.leaf_id = new_leaf_id


def create_branched_session(manager: Any, branch_from_id: str | None = None):
    branch_manager = manager.__class__.create(manager.cwd, manager.session_dir)
    branch_manager.header = manager.header
    branch_manager.session_name = manager.session_name
    branch_manager.entries = get_branch(manager, branch_from_id)
    branch_manager.entry_index = {entry.id: entry for entry in branch_manager.entries}
    for entry in branch_manager.entries:
        if entry.parent_id:
            branch_manager.parent_index.setdefault(entry.parent_id, []).append(entry.id)
    branch_manager.leaf_id = branch_manager.entries[-1].id if branch_manager.entries else None
    return branch_manager


def get_header(manager: Any) -> SessionHeader | None:
    return manager.header


def get_leaf_id(manager: Any) -> str | None:
    return manager.leaf_id


def get_leaf_entry(manager: Any) -> SessionEntry | None:
    if manager.leaf_id is None:
        return None
    return manager.entry_index.get(manager.leaf_id)


def get_entry(manager: Any, entry_id: str) -> SessionEntry | None:
    return manager.entry_index.get(entry_id)


def get_children(manager: Any, parent_id: str) -> list[SessionEntry]:
    return [manager.entry_index[child_id] for child_id in manager.parent_index.get(parent_id, []) if child_id in manager.entry_index]
