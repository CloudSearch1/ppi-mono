"""Compaction protocol and dataclass definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class CompactionPlan:
    cut_point_id: str | None = None
    tokens_before: int = 0
    keep_recent_tokens: int = 0
    summary_instructions: str = ""
    keep_recent_entries: int = 0
    preserve_branch_points: bool = True


@dataclass(slots=True)
class BranchSummary:
    from_id: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    created_from_compaction: bool = False


@dataclass(slots=True)
class CompactionResult:
    summary: str
    first_kept_entry_id: str
    tokens_before: int
    details: dict[str, Any] = field(default_factory=dict)
    cut_point_id: str | None = None
    branch_summary: BranchSummary | None = None


@dataclass(slots=True)
class CompactionInput:
    messages: list[Any] = field(default_factory=list)
    token_budget: int = 0
    instructions: str = ""


class CompactionStrategy(Protocol):
    def plan(self, compaction_input: CompactionInput) -> CompactionPlan:
        ...

    def compact(self, compaction_input: CompactionInput) -> CompactionResult:
        ...


__all__ = [
    "BranchSummary",
    "CompactionInput",
    "CompactionPlan",
    "CompactionResult",
    "CompactionStrategy",
]
