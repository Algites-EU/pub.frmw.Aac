from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Mapping, TypeVar

@dataclass(frozen=True, slots=True)
class AIcInvocationInput:
    invocation_id: str
    parent_invocation_id: str | None
    capability_id: str
    capability_version: int
    operation_id: str
    provider_instance_id: str
    arguments: Mapping[str, object] = field(default_factory=dict)
    operation_parameter_overrides: Mapping[str, object] = field(default_factory=dict)
    effective_operation_parameters: Mapping[str, object] = field(default_factory=dict)
    consumer_instance_id: str | None = None
    requirement_id: str | None = None
    locale: str | None = None
    def to_mapping(self) -> dict[str, object]:
        return {
            "InvocationId": self.invocation_id,
            "ParentInvocationId": self.parent_invocation_id,
            "CapabilityId": self.capability_id,
            "CapabilityVersion": self.capability_version,
            "OperationId": self.operation_id,
            "ProviderInstanceId": self.provider_instance_id,
            "Arguments": dict(self.arguments),
            "OperationParameterOverrides": dict(self.operation_parameter_overrides),
            "EffectiveOperationParameters": dict(self.effective_operation_parameters),
            "ConsumerInstanceId": self.consumer_instance_id,
            "RequirementId": self.requirement_id,
            "Locale": self.locale,
        }

    @classmethod
    def from_mapping(cls, aValue: Mapping[str, object]) -> "AIcInvocationInput":
        return cls(
            invocation_id=str(aValue["InvocationId"]),
            parent_invocation_id=(
                str(aValue["ParentInvocationId"]) if aValue.get("ParentInvocationId") is not None else None
            ),
            capability_id=str(aValue["CapabilityId"]),
            capability_version=int(aValue["CapabilityVersion"]),
            operation_id=str(aValue["OperationId"]),
            provider_instance_id=str(aValue["ProviderInstanceId"]),
            arguments=dict(aValue.get("Arguments", {})),
            operation_parameter_overrides=dict(aValue.get("OperationParameterOverrides", {})),
            effective_operation_parameters=dict(aValue.get("EffectiveOperationParameters", {})),
            consumer_instance_id=(
                str(aValue["ConsumerInstanceId"]) if aValue.get("ConsumerInstanceId") is not None else None
            ),
            requirement_id=str(aValue["RequirementId"]) if aValue.get("RequirementId") is not None else None,
            locale=str(aValue["Locale"]) if aValue.get("Locale") is not None else None,
        )

