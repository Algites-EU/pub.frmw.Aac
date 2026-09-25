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

class AIiOperationInteractionProviderToCaller(ABC):
    """Provider-facing half of one bidirectional, UI-neutral operation interaction."""

    @abstractmethod
    def declare_features(self, features: AIcOperationInteractionFeatures) -> None: ...

    @abstractmethod
    def report_events(self, events: tuple[AIcOperationInteractionEvent, ...]) -> None: ...

    def report(self, event: AIcOperationInteractionEvent) -> None:
        self.report_events((event,))

    @abstractmethod
    def state_result_changed(self) -> int:
        """Publish a new logical result revision without attaching its payload."""

    @abstractmethod
    def update_state_result(self, state_result: object) -> int:
        """Publish a new immutable result revision, attaching payload when the selected delivery mode requires it."""

    @abstractmethod
    def deliver_state_result(self, state_result: object, *, revision: int | None = None) -> None:
        """Deliver an existing result revision without creating another logical result revision."""

    @abstractmethod
    def caller_snapshot(self) -> AIcOperationInteractionCallerToProviderMessage: ...
