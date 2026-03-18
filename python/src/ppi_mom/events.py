"""Scheduled event contracts for mom."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias


@dataclass(slots=True)
class ImmediateEvent:
    type: Literal["immediate"] = "immediate"
    channel_id: str = ""
    text: str = ""


@dataclass(slots=True)
class OneShotEvent:
    type: Literal["one-shot"] = "one-shot"
    channel_id: str = ""
    text: str = ""
    at: str = ""


@dataclass(slots=True)
class PeriodicEvent:
    type: Literal["periodic"] = "periodic"
    channel_id: str = ""
    text: str = ""
    schedule: str = ""
    timezone: str = ""


MomEvent: TypeAlias = ImmediateEvent | OneShotEvent | PeriodicEvent
