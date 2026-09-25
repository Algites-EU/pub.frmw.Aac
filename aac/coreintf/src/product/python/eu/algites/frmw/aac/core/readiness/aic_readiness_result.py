from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from .aic_readiness_reason import AIcReadinessReason
from .ain_readiness_state import AInReadinessState

@dataclass(frozen=True, slots=True)
class AIcReadinessResult:
    state: AInReadinessState = AInReadinessState.READY
    reasons: tuple[AIcReadinessReason, ...] = ()

    def __post_init__(self) -> None:
        if self.state is AInReadinessState.READY and self.reasons:
            raise ValueError("READY readiness result must not contain reasons")
        if self.state is not AInReadinessState.READY and not self.reasons:
            raise ValueError("non-READY readiness result requires at least one reason")
