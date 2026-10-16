from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Mapping, TypeVar
from ..presentation.api import AIcDisplayText
from ..interaction_types import AInStateResultDeliveryMode

from .aic_operation_cancellation_acceptance import AIcOperationCancellationAcceptance
from .aic_operation_interaction_provider_to_caller_message import AIcOperationInteractionProviderToCallerMessage
from .aic_operation_interaction_caller_to_provider_message import AIcOperationInteractionCallerToProviderMessage
from .aic_operation_interaction_event import AIcOperationInteractionEvent
from .aic_operation_interaction_features import AIcOperationInteractionFeatures

P2CM = TypeVar("P2CM", bound=AIcOperationInteractionProviderToCallerMessage)


class AIiOperationInteractionProviderToCallerOnProvider(Generic[P2CM], ABC):
    """Provider endpoint: publish one P2C message at a time.

    Higher-level AAC features and state-result methods are retained here.
    An implementation may buffer publication until a transport can deliver it.
    """

    @abstractmethod
    def send_message(self, message: P2CM) -> None: ...

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

    @abstractmethod
    def accept_cancellation(self, reasons: frozenset[str]) -> AIcOperationCancellationAcceptance:
        """Irrevocably accept effective reasons from the last locally observed snapshot.

        This is a LOCAL decision; no synchronous callback/ack from Core is required.
        Acceptance evidence is delivered opportunistically by transport.
        """
