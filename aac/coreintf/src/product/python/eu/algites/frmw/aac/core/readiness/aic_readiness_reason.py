from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from .ain_readiness_state import AInReadinessState

@dataclass(frozen=True, slots=True)
class AIcReadinessReason:
    code: str
    message: str
    state: AInReadinessState
    requirement_id: str | None = None
    key: str | None = None

    def __post_init__(self) -> None:
        if not self.code or not self.message:
            raise ValueError("readiness reason code/message must not be empty")
        if self.state is AInReadinessState.READY:
            raise ValueError("READY does not require a readiness reason")
