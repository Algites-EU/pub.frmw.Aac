from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

from .ain_operation_interaction_detail_level import AInOperationInteractionDetailLevel
from .ain_operation_interaction_failure_detail_level import AInOperationInteractionFailureDetailLevel
from .ain_operation_interaction_mode import AInOperationInteractionMode

@dataclass(frozen=True, slots=True)
class AIcOperationInteractionCallerToProviderMessage:
    last_accepted_state_result_revision: int = 0
    interaction_mode: AInOperationInteractionMode = AInOperationInteractionMode.FOREGROUND
    cancellation_requested: bool = False
    detail_level: AInOperationInteractionDetailLevel = AInOperationInteractionDetailLevel.SUMMARY
    reporting_interval_ms: int | None = None
    failure_detail_level: AInOperationInteractionFailureDetailLevel = AInOperationInteractionFailureDetailLevel.BASIC
    state_result_delivery_mode: AInStateResultDeliveryMode = AInStateResultDeliveryMode.ON_DEMAND_COMPLETE
    state_result_request_id: int = 0

    def __post_init__(self) -> None:
        if self.last_accepted_state_result_revision < 0:
            raise ValueError("last_accepted_state_result_revision must be non-negative")
        if self.reporting_interval_ms is not None and self.reporting_interval_ms < 0:
            raise ValueError("reporting_interval_ms must be non-negative")
        if self.state_result_request_id < 0:
            raise ValueError("state_result_request_id must be non-negative")
