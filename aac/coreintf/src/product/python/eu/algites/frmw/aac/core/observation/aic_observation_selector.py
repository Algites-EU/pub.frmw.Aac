from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatchcase
from typing import Mapping

from .aic_observation_input import AIcObservationInput
from .ain_observation_phase import AInObservationPhase

@dataclass(frozen=True, slots=True)
class AIcObservationSelector:
    capability: str = "*"
    versions: tuple[int, ...] = ()
    operations: tuple[str, ...] = ()
    phases: tuple[AInObservationPhase, ...] = (AInObservationPhase.PRE, AInObservationPhase.POST)

    def matches(self, value: AIcObservationInput) -> bool:
        return (
            fnmatchcase(value.capability_id, self.capability)
            and (not self.versions or value.capability_version in self.versions)
            and (not self.operations or value.operation_id in self.operations)
            and value.phase in self.phases
        )
