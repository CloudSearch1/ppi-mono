"""Helpers for loading persisted JSON schemas."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import validate as jsonschema_validate


SCHEMA_VERSION = 1


SCHEMA_ROOT = Path(__file__).resolve().parents[3] / "schemas" / "coding-agent"
SCHEMA_REGISTRY_PATH = SCHEMA_ROOT / "schema-registry.json"


def schema_path(name: str) -> Path:
    filename = name if name.endswith(".schema.json") else f"{name}.schema.json"
    return SCHEMA_ROOT / filename


@lru_cache(maxsize=None)
def load_schema_registry() -> dict[str, Any]:
    if not SCHEMA_REGISTRY_PATH.exists():
        return {
            "version": SCHEMA_VERSION,
            "schemas": {
                path.stem.replace(".schema", ""): path.name for path in sorted(SCHEMA_ROOT.glob("*.schema.json"))
            },
        }
    return json.loads(SCHEMA_REGISTRY_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict[str, Any]:
    registry = load_schema_registry()
    schema_name = name if name.endswith(".schema.json") else f"{name}.schema.json"
    schema_file = (registry.get("schemas") or {}).get(schema_name) or (registry.get("schemas") or {}).get(name)
    if isinstance(schema_file, str):
        return json.loads(schema_path(schema_file).read_text(encoding="utf-8"))
    return json.loads(schema_path(name).read_text(encoding="utf-8"))


def available_schemas() -> list[str]:
    registry = load_schema_registry()
    schema_names = registry.get("schemas") or {}
    return sorted(schema_names.keys())


@lru_cache(maxsize=None)
def load_schema_by_name(name: str) -> dict[str, Any]:
    return load_schema(name)


def validate_schema(name: str, payload: Any) -> None:
    jsonschema_validate(payload, load_schema(name))


@lru_cache(maxsize=None)
def schema_registry() -> dict[str, Any]:
    return load_schema_registry()
