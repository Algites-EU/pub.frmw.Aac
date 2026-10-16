from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from datetime import datetime, timezone
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

from .aic_operation_cancellation_acceptance import AIcOperationCancellationAcceptance
from .aic_operation_interaction_event import AIcOperationInteractionEvent
from .aic_operation_interaction_features import AIcOperationInteractionFeatures
from .ain_operation_execution_state import AInOperationExecutionState

@dataclass(frozen=True, slots=True)
class AIcOperationInteractionProviderToCallerMessage:
    interaction_revision: int = 0
    execution_state: AInOperationExecutionState = AInOperationExecutionState.PENDING
    state_result_revision: int = 0
    state_result_payload_revision: int | None = None
    state_result: object | None = None
    events: tuple[AIcOperationInteractionEvent, ...] = ()
    features: AIcOperationInteractionFeatures = AIcOperationInteractionFeatures()
    published_at: datetime | None = None
    cancellation_acceptance: AIcOperationCancellationAcceptance | None = None

    def __post_init__(self) -> None:
        if self.published_at is not None and (self.published_at.tzinfo is None or self.published_at.utcoffset() is None):
            raise ValueError("published_at must have timezone information")
        if self.interaction_revision < 0:
            raise ValueError("interaction_revision must be non-negative")
        if self.state_result_revision < 0:
            raise ValueError("state_result_revision must be non-negative")
        if self.state_result_payload_revision is not None:
            if self.state_result_payload_revision < 1:
                raise ValueError("state_result_payload_revision must be >= 1 when present")
            if self.state_result_payload_revision > self.state_result_revision:
                raise ValueError("state_result_payload_revision cannot exceed state_result_revision")

    @property
    def state_result_included(self) -> bool:
        return self.state_result_payload_revision is not None
