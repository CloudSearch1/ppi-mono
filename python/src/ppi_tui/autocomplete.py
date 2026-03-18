"""Autocomplete provider contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(slots=True)
class AutocompleteItem:
    value: str
    label: str
    description: str | None = None


@dataclass(slots=True)
class SlashCommand:
    name: str
    description: str | None = None


class AutocompleteProvider(Protocol):
    def get_suggestions(self, text: str) -> list[AutocompleteItem]:
        ...

    def apply_completion(self, text: str, item: AutocompleteItem) -> str:
        ...


@dataclass(slots=True)
class CombinedAutocompleteProvider:
    commands: list[SlashCommand] = field(default_factory=list)
    base_path: Path | None = None

    def get_suggestions(self, text: str) -> list[AutocompleteItem]:
        raise NotImplementedError

    def apply_completion(self, text: str, item: AutocompleteItem) -> str:
        raise NotImplementedError
