from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

@dataclass(frozen=True, slots=True)
class AIcOperationInteractionFeatures:
    progress_reporting: bool = False
    cancellation: bool = False
    detail_level: bool = False
    reporting_interval: bool = False
    supported_state_result_delivery_modes: tuple[AInStateResultDeliveryMode, ...] = (
        AInStateResultDeliveryMode.ON_DEMAND_COMPLETE,
    )

    def __post_init__(self) -> None:
        if not self.supported_state_result_delivery_modes:
            raise ValueError("operation interaction must support at least one state-result delivery mode")
        if len(self.supported_state_result_delivery_modes) != len(set(self.supported_state_result_delivery_modes)):
            raise ValueError("supported state-result delivery modes must be unique")
        if AInStateResultDeliveryMode.ON_DEMAND_COMPLETE not in self.supported_state_result_delivery_modes:
            raise ValueError("every operation interaction must support ON_DEMAND_COMPLETE")
