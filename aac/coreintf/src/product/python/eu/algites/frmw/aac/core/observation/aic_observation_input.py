from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatchcase
from typing import Mapping

from .ain_observation_outcome import AInObservationOutcome
from .ain_observation_phase import AInObservationPhase

@dataclass(frozen=True, slots=True)
class AIcObservationInput:
    invocation_id: str
    parent_invocation_id: str | None
    phase: AInObservationPhase
    capability_id: str
    capability_version: int
    operation_id: str
    provider_instance_id: str
    arguments: Mapping[str, object] = field(default_factory=dict)
    outcome: AInObservationOutcome | None = None
    result: object | None = None
    error: Mapping[str, object] | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
