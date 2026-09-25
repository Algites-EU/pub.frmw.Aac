from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

@dataclass(frozen=True, slots=True)
class AIcCapabilityProviderOperationInteractionDescriptor:
    supported_state_result_delivery_modes: tuple[AInStateResultDeliveryMode, ...] = (
        AInStateResultDeliveryMode.ON_DEMAND_COMPLETE,
    )
    progress_reporting: bool = False
    cancellation: bool = False
    detail_level: bool = False
    reporting_interval: bool = False

    def __post_init__(self) -> None:
        if not self.supported_state_result_delivery_modes:
            raise ValueError("provider operation interaction must declare at least one state-result delivery mode")
        if len(self.supported_state_result_delivery_modes) != len(set(self.supported_state_result_delivery_modes)):
            raise ValueError("provider operation interaction state-result delivery modes must be unique")
        if AInStateResultDeliveryMode.ON_DEMAND_COMPLETE not in self.supported_state_result_delivery_modes:
            raise ValueError("provider operation interaction must support ON_DEMAND_COMPLETE")
