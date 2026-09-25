from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from ..readiness.api import AInReadinessState

from .ain_target_state_request_mode import AInTargetStateRequestMode

@dataclass(frozen=True, slots=True)
class AIcTargetStateRequest:
    component_id: str
    mode: AInTargetStateRequestMode = AInTargetStateRequestMode.LATEST_COMPATIBLE
    versions: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("target-state request component_id must not be empty")
        if any(version < 1 for version in self.versions):
            raise ValueError("target-state request versions must be >= 1")
        if self.mode is AInTargetStateRequestMode.EXACT and len(self.versions) != 1:
            raise ValueError("EXACT target-state request requires exactly one version")
        if self.mode is AInTargetStateRequestMode.ONE_OF and not self.versions:
            raise ValueError("ONE_OF target-state request requires at least one version")
        if self.mode is AInTargetStateRequestMode.LATEST_COMPATIBLE and self.versions:
            raise ValueError("LATEST_COMPATIBLE target-state request must not declare versions")

    @classmethod
    def exact(cls, component_id: str, version: int) -> "AIcTargetStateRequest":
        return cls(component_id, AInTargetStateRequestMode.EXACT, (version,))

    @classmethod
    def latest(cls, component_id: str) -> "AIcTargetStateRequest":
        return cls(component_id, AInTargetStateRequestMode.LATEST_COMPATIBLE, ())
