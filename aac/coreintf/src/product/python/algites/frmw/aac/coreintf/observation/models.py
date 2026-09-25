from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatchcase
from typing import Mapping


class AInObservationPhase(str, Enum):
    PRE = "PRE"
    POST = "POST"


class AInObservationOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


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


@dataclass(frozen=True, slots=True)
class AIcObservationOutput:
    accepted: bool = True
    diagnostic: str | None = None


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


@dataclass(frozen=True, slots=True)
class AIcObservationBinding:
    observer_instance_id: str
    selectors: tuple[AIcObservationSelector, ...]
