"""Model planning helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .config import PodConfig
from .models import ModelPlan


@dataclass(slots=True)
class ModelPlanner:
    def build_plan(self, pod: PodConfig, model: str, name: str) -> ModelPlan:
        raise NotImplementedError

