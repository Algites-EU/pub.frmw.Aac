from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatchcase
from typing import Mapping

from .aiig_observation_input_1 import AIigObservationInput_1
from .aing_observation_input_phase_1 import AIngObservationInputPhase_1

@dataclass(frozen=True, slots=True)
class AIcObservationSelector:
    capability: str = "*"
    versions: tuple[int, ...] = ()
    operations: tuple[str, ...] = ()
    phases: tuple[AIngObservationInputPhase_1, ...] = (AIngObservationInputPhase_1.PRE, AIngObservationInputPhase_1.POST)

    def matches(self, value: AIigObservationInput_1) -> bool:
        return (
            fnmatchcase(value.capability_id, self.capability)
            and (not self.versions or value.capability_version in self.versions)
            and (not self.operations or value.operation_id in self.operations)
            and value.phase in self.phases
        )
