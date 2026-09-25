from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

from .aic_capability_provider_operation_interaction_descriptor import AIcCapabilityProviderOperationInteractionDescriptor
from .aic_operation_parameter_definition_descriptor import AIcOperationParameterDefinitionDescriptor

@dataclass(frozen=True, slots=True)
class AIcCapabilityProviderOperationDescriptor:
    capability_id: str
    capability_version: int
    operation_id: str
    interaction: AIcCapabilityProviderOperationInteractionDescriptor
    parameters: tuple[AIcOperationParameterDefinitionDescriptor, ...] = ()

    def __post_init__(self) -> None:
        if not self.capability_id or self.capability_version < 1 or not self.operation_id:
            raise ValueError("provider operation requires capability id/version and operation id")
        ids = [item.id for item in self.parameters]
        if len(ids) != len(set(ids)):
            raise ValueError("operation parameter ids must be unique inside one provider operation")

    def parameter(self, parameter_id: str) -> AIcOperationParameterDefinitionDescriptor:
        for item in self.parameters:
            if item.id == parameter_id:
                return item
        raise KeyError(parameter_id)
