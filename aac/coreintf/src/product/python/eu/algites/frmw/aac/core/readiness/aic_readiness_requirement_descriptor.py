from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from .ain_readiness_requirement_source import AInReadinessRequirementSource
from .ain_readiness_state import AInReadinessState

@dataclass(frozen=True, slots=True)
class AIcReadinessRequirementDescriptor:
    id: str
    source: AInReadinessRequirementSource
    key: str
    missing_state: AInReadinessState = AInReadinessState.NOT_READY
    message: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.key:
            raise ValueError("readiness requirement id/key must not be empty")
        if self.missing_state is AInReadinessState.READY:
            raise ValueError("missing readiness requirement cannot declare READY")
