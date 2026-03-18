"""Model planning data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ModelPlan:
    model: str
    name: str
    memory: str | None = None
    context: str | None = None
    gpus: int | None = None
    vllm_args: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RunningModel:
    name: str
    model: str
    port: int
    pid: int
    gpu_indices: list[int] = field(default_factory=list)
