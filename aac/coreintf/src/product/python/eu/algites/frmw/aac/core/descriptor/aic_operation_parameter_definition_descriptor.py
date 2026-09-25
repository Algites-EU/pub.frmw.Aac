from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

from .aic_operation_parameter_enum_value_descriptor import AIcOperationParameterEnumValueDescriptor

@dataclass(frozen=True, slots=True)
class AIcOperationParameterDefinitionDescriptor:
    id: str
    name: AIcDisplayText
    description: AIcDisplayText
    value_schema: Mapping[str, object]
    enum_values: tuple[AIcOperationParameterEnumValueDescriptor, ...] = ()
    required: bool = False
    default: object | None = None
    has_default: bool = False
    component_configurable: bool = False
    instance_configurable: bool = False
    invocation_overridable: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("operation parameter id must not be empty")
        if not self.value_schema:
            raise ValueError("operation parameter value_schema must not be empty")
        enum_values = [item.value for item in self.enum_values]
        if len(enum_values) != len({repr(value) for value in enum_values}):
            raise ValueError("operation parameter enum values must be unique")
