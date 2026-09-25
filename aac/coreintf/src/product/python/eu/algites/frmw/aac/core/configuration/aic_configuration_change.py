from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_policy import AIcConfigurationPolicy
from .ain_configuration_mutation_operation import AInConfigurationMutationOperation

@dataclass(frozen=True, slots=True)
class AIcConfigurationChange:
    property_id: str
    operation: AInConfigurationMutationOperation
    value: object | None = None
    has_value: bool = False
    policy_modes: tuple[AIcConfigurationPolicy, ...] = ()

    def __post_init__(self) -> None:
        if not self.property_id:
            raise ValueError("configuration change property_id must not be empty")
        if self.operation is AInConfigurationMutationOperation.SET_VALUE:
            if not self.has_value:
                raise ValueError("SET_VALUE requires has_value=True so explicit null remains representable")
            if self.policy_modes:
                raise ValueError("SET_VALUE must not carry policy_modes")
        elif self.operation is AInConfigurationMutationOperation.SET_POLICY:
            if not self.policy_modes:
                raise ValueError("SET_POLICY requires at least one policy mode")
            if self.has_value or self.value is not None:
                raise ValueError("SET_POLICY must not carry a value")
        else:
            if self.has_value or self.value is not None or self.policy_modes:
                raise ValueError(f"{self.operation.value} must not carry value or policy_modes")
