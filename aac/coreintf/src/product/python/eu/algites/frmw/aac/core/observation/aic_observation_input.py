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

    def to_mapping(self) -> dict[str, object]:
        return {
            "InvocationId": self.invocation_id,
            "ParentInvocationId": self.parent_invocation_id,
            "Phase": self.phase.value,
            "CapabilityId": self.capability_id,
            "CapabilityVersion": self.capability_version,
            "OperationId": self.operation_id,
            "ProviderInstanceId": self.provider_instance_id,
            "Arguments": dict(self.arguments),
            "Outcome": self.outcome.value if self.outcome is not None else None,
            "Result": self.result,
            "Error": dict(self.error) if self.error is not None else None,
            "Metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, aValue: Mapping[str, object]) -> "AIcObservationInput":
        return cls(
            invocation_id=str(aValue["InvocationId"]),
            parent_invocation_id=(
                str(aValue["ParentInvocationId"]) if aValue.get("ParentInvocationId") is not None else None
            ),
            phase=AInObservationPhase(str(aValue["Phase"])),
            capability_id=str(aValue["CapabilityId"]),
            capability_version=int(aValue["CapabilityVersion"]),
            operation_id=str(aValue["OperationId"]),
            provider_instance_id=str(aValue["ProviderInstanceId"]),
            arguments=dict(aValue.get("Arguments", {})),
            outcome=(AInObservationOutcome(str(aValue["Outcome"])) if aValue.get("Outcome") is not None else None),
            result=aValue.get("Result"),
            error=(dict(aValue["Error"]) if isinstance(aValue.get("Error"), Mapping) else None),
            metadata=dict(aValue.get("Metadata", {})),
        )
