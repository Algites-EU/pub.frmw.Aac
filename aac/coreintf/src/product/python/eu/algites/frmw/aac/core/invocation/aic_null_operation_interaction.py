from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

from .aic_operation_interaction_caller_to_provider_message import AIcOperationInteractionCallerToProviderMessage
from .aic_operation_interaction_event import AIcOperationInteractionEvent
from .aic_operation_interaction_features import AIcOperationInteractionFeatures
from .aii_operation_interaction_provider_to_caller import AIiOperationInteractionProviderToCaller

class AIcNullOperationInteraction(AIiOperationInteractionProviderToCaller):
    """No-op interaction used by simple synchronous invocations without a caller callback."""

    def __init__(self) -> None:
        self._state_result_revision = 0
        self._caller = AIcOperationInteractionCallerToProviderMessage(
            state_result_delivery_mode=AInStateResultDeliveryMode.ON_DEMAND_COMPLETE,
        )

    def declare_features(self, features: AIcOperationInteractionFeatures) -> None:
        return None

    def report_events(self, events: tuple[AIcOperationInteractionEvent, ...]) -> None:
        return None

    def state_result_changed(self) -> int:
        self._state_result_revision += 1
        return self._state_result_revision

    def update_state_result(self, state_result: object) -> int:
        self._state_result_revision += 1
        return self._state_result_revision

    def deliver_state_result(self, state_result: object, *, revision: int | None = None) -> None:
        return None

    def caller_snapshot(self) -> AIcOperationInteractionCallerToProviderMessage:
        return self._caller
